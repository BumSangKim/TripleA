# database.py
# SQLite 기반 경제지표 저장소 - CRUD 및 로그 관리
import json
import re
import sqlite3
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pandas as pd
from datetime import date, datetime

# DB 파일은 project root/data/ 아래 (환경변수로 override 가능)
import os as _os
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = _os.getenv("DB_PATH", str(_PROJECT_ROOT / "data" / "economic_data.db"))


def _migrate_columns(conn: sqlite3.Connection):
    """기존 DB에 누락된 컬럼을 안전하게 추가 (idempotent)"""
    # ALTER TABLE ADD COLUMN 은 함수형 DEFAULT를 지원하지 않으므로 단순 타입만 사용
    migrations = [
        ("indicators", "observed_date", "TEXT"),
        ("indicators", "collected_at",  "TEXT"),   # DEFAULT 표현식 제거 (SQLite 제한)
        ("indicators", "frequency",     "TEXT"),
        ("indicators", "is_stale",      "INTEGER DEFAULT 0"),
        ("indicators", "source_detail", "TEXT"),
    ]
    for table, col, col_def in migrations:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # 이미 존재하는 컬럼 → 무시

    extra_migrations = [
        ("collector_runs", "finished_at", "TEXT"),
        ("event_releases", "revised", "REAL"),
        ("event_releases", "interpretation", "TEXT"),
    ]
    for table, col, col_def in extra_migrations:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
            conn.commit()
        except sqlite3.OperationalError:
            pass


def init_db(db_path: str = DB_PATH):
    """테이블 초기화 및 스키마 마이그레이션"""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    # ── 핵심 지표 테이블 ────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS indicators (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            date          TEXT NOT NULL,       -- 데이터 기준일 (YYYY-MM-DD)
            indicator     TEXT NOT NULL,
            value         REAL,
            source        TEXT,
            unit          TEXT,
            observed_date TEXT,                -- API가 보고한 실제 관측 날짜
            collected_at  TEXT DEFAULT (datetime('now','localtime')),
            frequency     TEXT,                -- 'daily' | 'weekly' | 'monthly' | 'quarterly'
            is_stale      INTEGER DEFAULT 0,   -- 1: 전일값 대체 (실제 수집 실패)
            source_detail TEXT,                -- 원본 API 응답 키/경로 등
            updated       TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(date, indicator)
        )
    """)

    # ── 기존 DB 스키마 마이그레이션 (새 컬럼 추가) ─────────────────
    _migrate_columns(conn)

    # ── 수집 로그 (기존 collect_log 유지) ──────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS collect_log (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date  TEXT,
            indicator TEXT,
            status    TEXT,   -- 'success' | 'fail'
            message   TEXT,
            created   TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # ── Collector 실행 결과 테이블 (P1) ────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS collector_runs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at       TEXT DEFAULT (datetime('now','localtime')),
            collector    TEXT NOT NULL,        -- e.g. 'ecos_keystat', 'fred', 'yahoo'
            status       TEXT NOT NULL,        -- 'ok' | 'partial' | 'fail'
            items_ok     INTEGER DEFAULT 0,
            items_fail   INTEGER DEFAULT 0,
            duration_ms  INTEGER,
            finished_at   TEXT,
            error_msg    TEXT
        )
    """)

    # ── API 원본 응답 저장 (P1) ─────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_observations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            collected_at TEXT DEFAULT (datetime('now','localtime')),
            source      TEXT NOT NULL,         -- e.g. 'FRED:CPIAUCSL'
            indicator   TEXT,
            raw_json    TEXT NOT NULL,         -- JSON 직렬화된 원본 응답
            obs_date    TEXT                   -- 관측 날짜 (알 수 있는 경우)
        )
    """)

    # ── 텔레그램 발송 이력 (P1: 중복 방지) ─────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS report_runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date TEXT NOT NULL UNIQUE,  -- YYYY-MM-DD (하루 1회 제한)
            sent_at     TEXT DEFAULT (datetime('now','localtime')),
            status      TEXT,                  -- 'ok' | 'fail'
            message_len INTEGER
        )
    """)

    # ── IR 파일링 테이블 (기존 유지) ────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ir_filings (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            accession TEXT NOT NULL UNIQUE,
            ticker    TEXT NOT NULL,
            company   TEXT,
            date      TEXT,
            form      TEXT,
            summary   TEXT,
            seen_at   TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # ── 경제 이벤트 일정 (P2) ───────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS economic_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            event_date  TEXT NOT NULL,         -- 발표 예정일
            event_time  TEXT,                  -- 발표 예정 시간 (UTC)
            event_name  TEXT NOT NULL,         -- 'US_CPI', 'NFP', 'PCE', 'FOMC'
            country     TEXT DEFAULT 'US',
            description TEXT,
            created_at  TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(event_date, event_name)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_releases (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id     INTEGER REFERENCES economic_events(id),
            released_at  TEXT DEFAULT (datetime('now','localtime')),
            actual       REAL,
            forecast     REAL,
            previous     REAL,
            revised      REAL,
            surprise     REAL,    -- actual - forecast
            interpretation TEXT,   -- hawkish | dovish | neutral
            unit         TEXT,
            source       TEXT
        )
    """)

    # 기존 event_releases 테이블에 새 컬럼 보강
    _migrate_columns(conn)

    # ── IR 키워드 멘션 저장 (AI 병목) ──────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ir_keyword_mentions (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            accession      TEXT NOT NULL,
            ticker         TEXT NOT NULL,
            filing_date    TEXT,
            keyword        TEXT NOT NULL,
            mention_count  INTEGER DEFAULT 0,
            created_at     TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(accession, keyword)
        )
    """)

    # ── 인덱스 ────────────────────────────────────────────────────
    # ── OHLCV 시장 데이터 (KIS/Yahoo 실시간/일봉) ──────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_data (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol     TEXT NOT NULL,          -- e.g. '005930', '^KS11', 'GC=F'
            date       TEXT NOT NULL,
            open       REAL,
            high       REAL,
            low        REAL,
            close      REAL NOT NULL,
            volume     REAL,
            source     TEXT,                   -- 'KIS' | 'Yahoo' | 'ECOS'
            created_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(symbol, date)
        )
    """)

    # ── 기술적 지표 피처 스냅샷 ──────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS features (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            indicator    TEXT NOT NULL,
            computed_at  TEXT DEFAULT (datetime('now','localtime')),
            sma5         REAL,
            sma20        REAL,
            ema12        REAL,
            rsi14        REAL,
            macd         REAL,
            macd_signal  REAL,
            macd_hist    REAL,
            bb_upper     REAL,
            bb_middle    REAL,
            bb_lower     REAL,
            bb_bandwidth REAL,
            n_obs        INTEGER,
            rsi_signal   TEXT,  -- OVERBOUGHT | OVERSOLD | NEUTRAL
            ma_signal    TEXT,  -- GOLDEN_CROSS | DEAD_CROSS
            macd_bias    TEXT   -- BULLISH | BEARISH
        )
    """)

    # ── 매매 신호 테이블 ─────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at   TEXT DEFAULT (datetime('now','localtime')),
            indicator    TEXT NOT NULL,
            signal_type  TEXT NOT NULL,        -- 'BUY' | 'SELL' | 'HOLD'
            strategy     TEXT,                 -- 'golden_cross' | 'rsi' | 'macd'
            confidence   REAL,                 -- 0.0 ~ 1.0
            price        REAL,
            detail       TEXT,                 -- 판단 근거 (JSON)
            notified     INTEGER DEFAULT 0     -- 텔레그램 전송 여부
        )
    """)

    # ── 주문 실행 이력 ─────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at     TEXT DEFAULT (datetime('now','localtime')),
            broker_order_id TEXT,
            symbol         TEXT NOT NULL,
            side           TEXT NOT NULL,
            qty            REAL NOT NULL,
            price          REAL,
            status         TEXT NOT NULL,
            broker         TEXT,
            strategy       TEXT,
            signal_id      INTEGER,
            reason         TEXT
        )
    """)

    # ── 기업 분기 재무 데이터 (Valuation Layer) ─────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS company_fundamentals (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker            TEXT NOT NULL,
            period            TEXT NOT NULL,     -- YYYY-MM-DD (분기 마지막일)
            revenue           REAL,              -- USD
            ebitda            REAL,              -- USD
            net_income        REAL,              -- USD
            equity            REAL,              -- USD (Book Value)
            debt              REAL,              -- USD (Total Debt)
            cash              REAL,              -- USD
            roic              REAL,              -- % (Return on Invested Capital)
            roe               REAL,              -- %
            revenue_growth_yoy REAL,             -- % YoY
            ebitda_margin     REAL,              -- % (EBITDA/Revenue)
            debt_ratio        REAL,              -- Debt/Equity
            source            TEXT DEFAULT 'FMP',
            updated_at        TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(ticker, period)
        )
    """)

    # ── 기업 시장 멀티플 스냅샷 (주간) ──────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS company_multiples (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            date             TEXT NOT NULL,
            ticker           TEXT NOT NULL,
            sector           TEXT,
            close_price      REAL,
            market_cap       REAL,              -- USD billion
            enterprise_value REAL,              -- USD billion
            ev_ebitda        REAL,              -- EV/EBITDA multiple
            pe_ratio         REAL,              -- Trailing P/E
            pb_ratio         REAL,              -- Price/Book
            ps_ratio         REAL,              -- Price/Sales
            source           TEXT DEFAULT 'Yahoo',
            updated_at       TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(date, ticker)
        )
    """)

    # ── 병목지수 시계열 ──────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bottleneck_scores (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            date             TEXT NOT NULL UNIQUE,
            z_pmi_sdt        REAL,   -- 공급망 압력 (GSCPI)
            z_wti            REAL,   -- 원자재 비용 압력 (WTI z-score)
            z_us10y          REAL,   -- 금리 부담 (US10Y z-score)
            z_inflation      REAL,   -- 물가 압력 (CPI YoY z-score)
            bottleneck_index REAL,   -- 가중 합성 병목지수
            updated_at       TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # ── 밸류에이션 결과 ─────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS valuation_results (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            date                 TEXT NOT NULL,
            ticker               TEXT NOT NULL,
            sector               TEXT,
            current_ev_ebitda    REAL,
            fair_ev_ebitda       REAL,
            mispricing_ev_ebitda REAL,  -- (current-fair)/fair
            current_per          REAL,
            fair_per             REAL,
            mispricing_per       REAL,
            current_pbr          REAL,
            fair_pbr             REAL,
            mispricing_pbr       REAL,
            overvaluation_score  REAL,  -- 복합 고평가 스코어
            valuation_signal     TEXT,  -- '고평가'|'저평가'|'적정'
            model_type           TEXT DEFAULT 'heuristic',
            bottleneck_used      REAL,
            updated_at           TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(date, ticker)
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_indicators_date ON indicators(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_indicators_indicator ON indicators(indicator)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_indicators_stale ON indicators(is_stale)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ir_filings_ticker ON ir_filings(ticker)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ir_keyword_ticker ON ir_keyword_mentions(ticker)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_raw_obs_source ON raw_observations(source)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_date ON economic_events(event_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_market_data_symbol ON market_data(symbol, date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_features_indicator ON features(indicator)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_company_fund ON company_fundamentals(ticker, period)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_company_mult ON company_multiples(ticker, date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bottleneck ON bottleneck_scores(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_valuation ON valuation_results(date, ticker)")
    conn.commit()
    conn.close()


def is_filing_seen(accession: str, db_path: str = DB_PATH) -> bool:
    """해당 accession 번호가 이미 DB에 있는지 확인"""
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT 1 FROM ir_filings WHERE accession=?", (accession,)
    ).fetchone()
    conn.close()
    return row is not None


def save_ir_filing(filing: dict, summary: str, db_path: str = DB_PATH):
    """IR 파일링 및 요약 저장"""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT OR IGNORE INTO ir_filings (accession, ticker, company, date, form, summary)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            filing["accession"],
            filing["ticker"],
            filing["company"],
            filing["date"],
            filing["form"],
            summary,
        ),
    )
    conn.commit()
    conn.close()


def upsert_indicator(
    date_str: str,
    indicator: str,
    value: float,
    source: str,
    unit: str = "",
    db_path: str = DB_PATH,
    is_stale: int = 0,
    frequency: str = None,
    source_detail: str = None,
    observed_date: str = None,
):
    """지표 저장 (중복 시 업데이트). is_stale=1이면 전일 대체값임을 표시."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO indicators
            (date, indicator, value, source, unit, is_stale, frequency, source_detail, observed_date, collected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
        ON CONFLICT(date, indicator) DO UPDATE SET
            value        = excluded.value,
            source       = excluded.source,
            is_stale     = excluded.is_stale,
            frequency    = COALESCE(excluded.frequency, frequency),
            source_detail= COALESCE(excluded.source_detail, source_detail),
            observed_date= COALESCE(excluded.observed_date, observed_date),
            collected_at = excluded.collected_at,
            updated      = datetime('now','localtime')
        """,
        (date_str, indicator, value, source, unit, is_stale, frequency, source_detail, observed_date),
    )
    conn.commit()
    conn.close()


def get_latest(indicator: str, n: int = 30, db_path: str = DB_PATH) -> pd.DataFrame:
    """최근 n개 데이터 조회"""
    conn = sqlite3.connect(db_path)
    df = pd.read_sql(
        "SELECT date, value FROM indicators WHERE indicator=? ORDER BY date DESC LIMIT ?",
        conn,
        params=(indicator, n),
    )
    conn.close()
    return df.sort_values("date").reset_index(drop=True)


def get_previous_value(indicator: str, db_path: str = DB_PATH):
    """최신 데이터 조회 (수집 실패 시 대체용)"""
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "SELECT value FROM indicators WHERE indicator=? ORDER BY date DESC LIMIT 1",
        (indicator,),
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def log_collect(
    indicator: str,
    status: str,
    message: str = "",
    db_path: str = DB_PATH,
):
    """수집 결과 로그 기록"""
    today = date.today().isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO collect_log (run_date, indicator, status, message) VALUES (?,?,?,?)",
        (today, indicator, status, message),
    )
    conn.commit()
    conn.close()


def get_collect_stats(run_date: str = None, db_path: str = DB_PATH) -> dict:
    """당일 수집 통계 조회"""
    if run_date is None:
        run_date = date.today().isoformat()
    conn = sqlite3.connect(db_path)
    logs = conn.execute(
        "SELECT status, COUNT(*) FROM collect_log WHERE run_date=? GROUP BY status",
        (run_date,),
    ).fetchall()
    conn.close()
    return dict(logs)


# ── Collector 실행 기록 ──────────────────────────────────────────────────────

def log_collector_run(
    collector: str,
    status: str,
    items_ok: int = 0,
    items_fail: int = 0,
    duration_ms: int = None,
    started_at: str = None,
    finished_at: str = None,
    error_msg: str = None,
    db_path: str = DB_PATH,
):
    """collector 실행 결과를 collector_runs 테이블에 기록"""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO collector_runs
            (run_at, collector, status, items_ok, items_fail, duration_ms, finished_at, error_msg)
        VALUES (COALESCE(?, datetime('now','localtime')), ?, ?, ?, ?, ?, ?, ?)
        """,
        (started_at, collector, status, items_ok, items_fail, duration_ms, finished_at, error_msg),
    )
    conn.commit()
    conn.close()


# ── 원본 응답 저장 ──────────────────────────────────────────────────────────

_SECRET_KEY_RE = re.compile(
    r"^(api[_-]?key|apikey|access[_-]?token|accesstoken|token|secret|client[_-]?secret|auth|authorization|key)$",
    re.I,
)


def mask_sensitive_url(url: str) -> str:
    """URL query string 안의 API 키성 파라미터를 마스킹한다."""
    try:
        parts = urlsplit(url)
    except Exception:
        return url
    if not parts.query:
        return url
    changed = False
    pairs = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if _SECRET_KEY_RE.search(key):
            pairs.append((key, "***MASKED***"))
            changed = True
        else:
            pairs.append((key, value))
    if not changed:
        return url
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(pairs), parts.fragment))


def mask_sensitive_data(data):
    """API 키/토큰/시크릿처럼 보이는 값은 raw 저장 전에 마스킹한다."""
    if isinstance(data, dict):
        return {
            key: "***MASKED***" if _SECRET_KEY_RE.search(str(key)) else mask_sensitive_data(value)
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [mask_sensitive_data(item) for item in data]
    if isinstance(data, tuple):
        return tuple(mask_sensitive_data(item) for item in data)
    if isinstance(data, str):
        return mask_sensitive_url(data)
    return data


def save_raw_observation(
    source: str,
    raw_data,
    indicator: str = None,
    obs_date: str = None,
    db_path: str = DB_PATH,
):
    """API 원본 응답을 JSON으로 raw_observations 테이블에 저장"""
    raw_data = mask_sensitive_data(deepcopy(raw_data))
    try:
        raw_json = json.dumps(raw_data, ensure_ascii=False, default=str)
    except Exception:
        raw_json = str(mask_sensitive_data(raw_data))
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO raw_observations (source, indicator, raw_json, obs_date)
        VALUES (?, ?, ?, ?)
        """,
        (source, indicator, raw_json, obs_date),
    )
    conn.commit()
    conn.close()


# ── 보고서 발송 이력 ─────────────────────────────────────────────────────────

def is_report_sent_today(db_path: str = DB_PATH) -> bool:
    """오늘 날짜로 보고서가 이미 발송됐는지 확인"""
    today = date.today().isoformat()
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT 1 FROM report_runs WHERE report_date=? AND status='ok'", (today,)
    ).fetchone()
    conn.close()
    return row is not None


def mark_report_sent(message_len: int = 0, status: str = "ok", db_path: str = DB_PATH):
    """오늘 날짜로 보고서 발송 성공을 기록 (중복 방지)"""
    today = date.today().isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT OR REPLACE INTO report_runs (report_date, status, message_len)
        VALUES (?, ?, ?)
        """,
        (today, status, message_len),
    )
    conn.commit()
    conn.close()


# ── 경제 이벤트 관리 ─────────────────────────────────────────────────────────

def upsert_economic_event(
    event_date: str,
    event_name: str,
    event_time: str = None,
    country: str = "US",
    description: str = None,
    db_path: str = DB_PATH,
) -> int:
    """경제 이벤트 일정 저장. 이미 존재하면 description만 업데이트. 행 id 반환."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO economic_events (event_date, event_name, event_time, country, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(event_date, event_name) DO UPDATE SET
            description = COALESCE(excluded.description, description),
            event_time  = COALESCE(excluded.event_time, event_time)
        """,
        (event_date, event_name, event_time, country, description),
    )
    row_id = conn.execute(
        "SELECT id FROM economic_events WHERE event_date=? AND event_name=?",
        (event_date, event_name),
    ).fetchone()[0]
    conn.commit()
    conn.close()
    return row_id


def save_event_release(
    event_id: int,
    actual: float = None,
    forecast: float = None,
    previous: float = None,
    revised: float = None,
    unit: str = None,
    source: str = None,
    event_name: str = None,
    db_path: str = DB_PATH,
):
    """경제 이벤트 실제 발표값 저장"""
    surprise = None
    if actual is not None and forecast is not None:
        surprise = round(actual - forecast, 4)
    conn = sqlite3.connect(db_path)
    if event_name is None and event_id is not None:
        row = conn.execute("SELECT event_name FROM economic_events WHERE id=?", (event_id,)).fetchone()
        event_name = row[0] if row else None
    interpretation = interpret_event_surprise(event_name, surprise)
    conn.execute(
        """
        INSERT INTO event_releases
            (event_id, actual, forecast, previous, revised, surprise, interpretation, unit, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (event_id, actual, forecast, previous, revised, surprise, interpretation, unit, source),
    )
    conn.commit()
    conn.close()


def interpret_event_surprise(event_name: str = None, surprise: float = None) -> str | None:
    """서프라이즈 방향을 금리 관점으로 해석한다."""
    if surprise is None or not event_name:
        return None
    if surprise == 0:
        return "neutral"
    name = event_name.lower()
    is_inflation_or_wage = any(
        token in name
        for token in ("cpi", "pce", "ppi", "average_hourly_earnings", "hourly", "wage", "earnings")
    )
    is_unemployment = "unemployment" in name or "jobless" in name
    if is_inflation_or_wage:
        return "hawkish" if surprise > 0 else "dovish"
    if is_unemployment:
        return "dovish" if surprise > 0 else "hawkish"
    return None


def get_upcoming_events(days_ahead: int = 7, db_path: str = DB_PATH) -> list[dict]:
    """향후 n일 내 예정된 경제 이벤트 목록 반환"""
    from datetime import timedelta
    today = date.today().isoformat()
    end_date = (date.today() + timedelta(days=days_ahead)).isoformat()
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        """
        SELECT e.id, e.event_date, e.event_time, e.event_name, e.country, e.description,
               r.actual, r.forecast, r.previous, r.revised, r.surprise, r.interpretation
        FROM economic_events e
        LEFT JOIN event_releases r ON r.event_id = e.id
        WHERE e.event_date BETWEEN ? AND ?
        ORDER BY e.event_date, e.event_time
        """,
        (today, end_date),
    ).fetchall()
    conn.close()
    cols = ["id", "event_date", "event_time", "event_name", "country", "description",
            "actual", "forecast", "previous", "revised", "surprise", "interpretation"]
    return [dict(zip(cols, r)) for r in rows]


def save_ir_keyword_mentions(
    filing: dict,
    keyword_counts: dict[str, int],
    db_path: str = DB_PATH,
):
    """파일링별 AI 병목 키워드 등장 횟수 저장."""
    if not filing or not keyword_counts:
        return
    accession = filing.get("accession")
    ticker = filing.get("ticker")
    if not accession or not ticker:
        return
    conn = sqlite3.connect(db_path)
    for keyword, count in keyword_counts.items():
        conn.execute(
            """
            INSERT INTO ir_keyword_mentions
                (accession, ticker, filing_date, keyword, mention_count)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(accession, keyword) DO UPDATE SET
                ticker = excluded.ticker,
                filing_date = excluded.filing_date,
                mention_count = excluded.mention_count
            """,
            (accession, ticker, filing.get("date"), keyword, int(count)),
        )
    conn.commit()
    conn.close()


# ── 기술적 지표 피처 저장 ────────────────────────────────────────────────────

def save_features(features: dict, db_path: str = DB_PATH) -> None:
    """기술적 지표 피처 스냅샷 저장."""
    if not features or not features.get("indicator"):
        return
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO features
            (indicator, sma5, sma20, ema12, rsi14, macd, macd_signal, macd_hist,
             bb_upper, bb_middle, bb_lower, bb_bandwidth, n_obs,
             rsi_signal, ma_signal, macd_bias)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            features.get("indicator"), features.get("sma5"), features.get("sma20"),
            features.get("ema12"), features.get("rsi14"), features.get("macd"),
            features.get("macd_signal"), features.get("macd_hist"),
            features.get("bb_upper"), features.get("bb_middle"), features.get("bb_lower"),
            features.get("bb_bandwidth"), features.get("n_obs"),
            features.get("rsi_signal"), features.get("ma_signal"), features.get("macd_bias"),
        ),
    )
    conn.commit()
    conn.close()


def save_signal(
    indicator: str,
    signal_type: str,
    strategy: str,
    confidence: float,
    price: float = None,
    detail: str = None,
    db_path: str = DB_PATH,
) -> int:
    """매매 신호 저장. 저장된 row id 반환."""
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        """
        INSERT INTO signals (indicator, signal_type, strategy, confidence, price, detail)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (indicator, signal_type, strategy, round(confidence, 4), price, detail),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def mark_signal_notified(signal_id: int, db_path: str = DB_PATH) -> None:
    """텔레그램 전송 완료 표시."""
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE signals SET notified=1 WHERE id=?", (signal_id,))
    conn.commit()
    conn.close()


def get_unnotified_signals(db_path: str = DB_PATH) -> list[dict]:
    """아직 텔레그램으로 전송하지 않은 신호 목록."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        """
        SELECT id, indicator, signal_type, strategy, confidence, price, detail, created_at
        FROM signals WHERE notified = 0
        ORDER BY created_at DESC
        """,
    ).fetchall()
    conn.close()
    cols = ["id", "indicator", "signal_type", "strategy", "confidence", "price", "detail", "created_at"]
    return [dict(zip(cols, r)) for r in rows]


def upsert_market_data(
    symbol: str,
    date_str: str,
    close: float,
    open_: float = None,
    high: float = None,
    low: float = None,
    volume: float = None,
    source: str = None,
    db_path: str = DB_PATH,
) -> None:
    """OHLCV 시장 데이터 upsert."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO market_data (symbol, date, open, high, low, close, volume, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, date) DO UPDATE SET
            open   = COALESCE(excluded.open,   open),
            high   = COALESCE(excluded.high,   high),
            low    = COALESCE(excluded.low,    low),
            close  = excluded.close,
            volume = COALESCE(excluded.volume, volume),
            source = excluded.source
        """,
        (symbol, date_str, open_, high, low, close, volume, source),
    )
    conn.commit()
    conn.close()


def record_order(order: dict, db_path: str = DB_PATH) -> int:
    """주문 실행 결과를 DB에 기록하고 row id를 반환."""
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        """
        INSERT INTO orders
            (broker_order_id, symbol, side, qty, price, status, broker, strategy, signal_id, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order.get("broker_order_id") or order.get("order_id"),
            order["symbol"],
            order["side"],
            float(order["qty"]),
            order.get("price"),
            order["status"],
            order.get("broker"),
            order.get("strategy"),
            order.get("signal_id"),
            order.get("reason"),
        ),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


# ── Valuation Layer CRUD ─────────────────────────────────────────────────────

def upsert_company_fundamentals(
    ticker: str,
    period: str,
    revenue: float = None,
    ebitda: float = None,
    net_income: float = None,
    equity: float = None,
    debt: float = None,
    cash: float = None,
    roic: float = None,
    roe: float = None,
    revenue_growth_yoy: float = None,
    ebitda_margin: float = None,
    debt_ratio: float = None,
    source: str = "FMP",
    db_path: str = DB_PATH,
):
    """기업 분기 재무 데이터 저장/업데이트"""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO company_fundamentals
            (ticker, period, revenue, ebitda, net_income, equity, debt, cash,
             roic, roe, revenue_growth_yoy, ebitda_margin, debt_ratio, source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(ticker, period) DO UPDATE SET
            revenue=COALESCE(excluded.revenue, revenue),
            ebitda=COALESCE(excluded.ebitda, ebitda),
            net_income=COALESCE(excluded.net_income, net_income),
            equity=COALESCE(excluded.equity, equity),
            debt=COALESCE(excluded.debt, debt),
            cash=COALESCE(excluded.cash, cash),
            roic=COALESCE(excluded.roic, roic),
            roe=COALESCE(excluded.roe, roe),
            revenue_growth_yoy=COALESCE(excluded.revenue_growth_yoy, revenue_growth_yoy),
            ebitda_margin=COALESCE(excluded.ebitda_margin, ebitda_margin),
            debt_ratio=COALESCE(excluded.debt_ratio, debt_ratio),
            updated_at=datetime('now','localtime')
        """,
        (ticker, period, revenue, ebitda, net_income, equity, debt, cash,
         roic, roe, revenue_growth_yoy, ebitda_margin, debt_ratio, source),
    )
    conn.commit()
    conn.close()


def upsert_company_multiples(
    date_str: str,
    ticker: str,
    sector: str = None,
    close_price: float = None,
    market_cap: float = None,
    enterprise_value: float = None,
    ev_ebitda: float = None,
    pe_ratio: float = None,
    pb_ratio: float = None,
    ps_ratio: float = None,
    source: str = "Yahoo",
    db_path: str = DB_PATH,
):
    """기업 시장 멀티플 스냅샷 저장/업데이트"""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO company_multiples
            (date, ticker, sector, close_price, market_cap, enterprise_value,
             ev_ebitda, pe_ratio, pb_ratio, ps_ratio, source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(date, ticker) DO UPDATE SET
            sector=COALESCE(excluded.sector, sector),
            close_price=COALESCE(excluded.close_price, close_price),
            market_cap=COALESCE(excluded.market_cap, market_cap),
            enterprise_value=COALESCE(excluded.enterprise_value, enterprise_value),
            ev_ebitda=COALESCE(excluded.ev_ebitda, ev_ebitda),
            pe_ratio=COALESCE(excluded.pe_ratio, pe_ratio),
            pb_ratio=COALESCE(excluded.pb_ratio, pb_ratio),
            ps_ratio=COALESCE(excluded.ps_ratio, ps_ratio),
            updated_at=datetime('now','localtime')
        """,
        (date_str, ticker, sector, close_price, market_cap, enterprise_value,
         ev_ebitda, pe_ratio, pb_ratio, ps_ratio, source),
    )
    conn.commit()
    conn.close()


def save_bottleneck_score(
    date_str: str,
    bottleneck_index: float,
    z_pmi_sdt: float = None,
    z_wti: float = None,
    z_us10y: float = None,
    z_inflation: float = None,
    db_path: str = DB_PATH,
):
    """병목지수 저장"""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO bottleneck_scores
            (date, bottleneck_index, z_pmi_sdt, z_wti, z_us10y, z_inflation)
        VALUES (?,?,?,?,?,?)
        ON CONFLICT(date) DO UPDATE SET
            bottleneck_index=excluded.bottleneck_index,
            z_pmi_sdt=COALESCE(excluded.z_pmi_sdt, z_pmi_sdt),
            z_wti=COALESCE(excluded.z_wti, z_wti),
            z_us10y=COALESCE(excluded.z_us10y, z_us10y),
            z_inflation=COALESCE(excluded.z_inflation, z_inflation),
            updated_at=datetime('now','localtime')
        """,
        (date_str, bottleneck_index, z_pmi_sdt, z_wti, z_us10y, z_inflation),
    )
    conn.commit()
    conn.close()


def upsert_valuation_result(
    date_str: str,
    ticker: str,
    sector: str = None,
    current_ev_ebitda: float = None,
    fair_ev_ebitda: float = None,
    mispricing_ev_ebitda: float = None,
    current_per: float = None,
    fair_per: float = None,
    mispricing_per: float = None,
    current_pbr: float = None,
    fair_pbr: float = None,
    mispricing_pbr: float = None,
    overvaluation_score: float = None,
    valuation_signal: str = None,
    model_type: str = "heuristic",
    bottleneck_used: float = None,
    db_path: str = DB_PATH,
):
    """밸류에이션 결과 저장/업데이트"""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO valuation_results
            (date, ticker, sector, current_ev_ebitda, fair_ev_ebitda, mispricing_ev_ebitda,
             current_per, fair_per, mispricing_per, current_pbr, fair_pbr, mispricing_pbr,
             overvaluation_score, valuation_signal, model_type, bottleneck_used)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(date, ticker) DO UPDATE SET
            sector=COALESCE(excluded.sector, sector),
            current_ev_ebitda=COALESCE(excluded.current_ev_ebitda, current_ev_ebitda),
            fair_ev_ebitda=COALESCE(excluded.fair_ev_ebitda, fair_ev_ebitda),
            mispricing_ev_ebitda=COALESCE(excluded.mispricing_ev_ebitda, mispricing_ev_ebitda),
            current_per=COALESCE(excluded.current_per, current_per),
            fair_per=COALESCE(excluded.fair_per, fair_per),
            mispricing_per=COALESCE(excluded.mispricing_per, mispricing_per),
            current_pbr=COALESCE(excluded.current_pbr, current_pbr),
            fair_pbr=COALESCE(excluded.fair_pbr, fair_pbr),
            mispricing_pbr=COALESCE(excluded.mispricing_pbr, mispricing_pbr),
            overvaluation_score=COALESCE(excluded.overvaluation_score, overvaluation_score),
            valuation_signal=COALESCE(excluded.valuation_signal, valuation_signal),
            model_type=excluded.model_type,
            bottleneck_used=COALESCE(excluded.bottleneck_used, bottleneck_used),
            updated_at=datetime('now','localtime')
        """,
        (date_str, ticker, sector, current_ev_ebitda, fair_ev_ebitda, mispricing_ev_ebitda,
         current_per, fair_per, mispricing_per, current_pbr, fair_pbr, mispricing_pbr,
         overvaluation_score, valuation_signal, model_type, bottleneck_used),
    )
    conn.commit()
    conn.close()


def get_latest_valuation_results(db_path: str = DB_PATH) -> pd.DataFrame:
    """가장 최근 날짜의 밸류에이션 결과 전체 조회"""
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(
            """
            SELECT v.*
            FROM valuation_results v
            INNER JOIN (
                SELECT ticker, MAX(date) AS max_date FROM valuation_results GROUP BY ticker
            ) latest ON v.ticker=latest.ticker AND v.date=latest.max_date
            ORDER BY v.overvaluation_score DESC
            """,
            conn,
        )
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df


def get_bottleneck_history(n: int = 52, db_path: str = DB_PATH) -> pd.DataFrame:
    """병목지수 시계열 조회 (최근 n주)"""
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(
            "SELECT date, bottleneck_index, z_pmi_sdt, z_wti, z_us10y, z_inflation "
            "FROM bottleneck_scores ORDER BY date DESC LIMIT ?",
            conn, params=(n,),
        )
        df = df.sort_values("date").reset_index(drop=True)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df


def get_latest_fundamentals(ticker: str, db_path: str = DB_PATH) -> dict:
    """기업 최신 분기 재무 데이터 조회"""
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        """SELECT * FROM company_fundamentals WHERE ticker=?
           ORDER BY period DESC LIMIT 1""",
        (ticker,),
    ).fetchone()
    conn.close()
    if row is None:
        return {}
    cols = ["id", "ticker", "period", "revenue", "ebitda", "net_income", "equity",
            "debt", "cash", "roic", "roe", "revenue_growth_yoy", "ebitda_margin",
            "debt_ratio", "source", "updated_at"]
    return dict(zip(cols, row))
