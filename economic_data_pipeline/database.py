# database.py
# SQLite 기반 경제지표 저장소 - CRUD 및 로그 관리
import sqlite3
import pandas as pd
from datetime import date

DB_PATH = "economic_data.db"


def init_db(db_path: str = DB_PATH):
    """테이블 초기화"""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS indicators (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            date      TEXT NOT NULL,
            indicator TEXT NOT NULL,
            value     REAL,
            source    TEXT,
            unit      TEXT,
            updated   TEXT DEFAULT (datetime('now', 'localtime')),
            UNIQUE(date, indicator)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS collect_log (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date  TEXT,
            indicator TEXT,
            status    TEXT,   -- 'success' or 'fail'
            message   TEXT,
            created   TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_indicators_date ON indicators(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_indicators_indicator ON indicators(indicator)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ir_filings_ticker ON ir_filings(ticker)")
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
):
    """지표 저장 (중복 시 업데이트)"""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO indicators (date, indicator, value, source, unit)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(date, indicator) DO UPDATE SET
            value  = excluded.value,
            source = excluded.source,
            updated = datetime('now', 'localtime')
        """,
        (date_str, indicator, value, source, unit),
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
