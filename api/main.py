"""
api/main.py
FastAPI 대시보드 API 서버
실행: cd /Users/bumsangkim/Dev/TripleA && uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import List, Optional

import csv
import io
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from .db import get_conn, ensure_dashboard_tables
from .models import (
    DashboardSummary, MacroIndicator, AccountSummary, AllocationItem,
    TargetItem, TargetUpdate, SuggestionItem, TopMover, CalendarEvent,
    AlertItem, Insights, DocumentItem, TokenResponse, ModeInfo,
    AccountPolicyItem, AccountSnapshotCreate, AccountSnapshotItem,
    RebalanceResultItem, RebalanceRunResponse, ProviderSyncResult,
)
from .kis import KISAPIError, KISConfigError
from .modes import TradingMode, normalize_mode
from .providers import provider_router
from .services import (
    get_macro_indicators, get_rebalancing_suggestions,
    get_recent_alerts, get_kpi_summary,
    get_calendar_events, build_insights, generate_target_alerts,
    get_account_policies, save_manual_snapshot,
    get_account_snapshots, set_account_rebalancing_inclusion,
    record_rebalance_results, get_rebalance_results,
)

logger = logging.getLogger("uvicorn.error")


def _mode_info(mode: TradingMode) -> ModeInfo:
    return provider_router.get(mode).mode_info()


def _parse_mode(mode: Optional[str]) -> TradingMode:
    try:
        return normalize_mode(mode)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


def _ensure_user_write_mode(mode: TradingMode):
    try:
        provider_router.get(mode).assert_user_write_allowed()
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e

# ── JWT 설정 ────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET", "triplea-dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

try:
    from jose import JWTError, jwt
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

# ── App 초기화 ───────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dashboard_tables()
    with get_conn() as conn:
        n = generate_target_alerts(conn)
    if n:
        logger.info(f"[startup] {n}개 목표 이탈 알림 생성")
    yield

app = FastAPI(
    title="TripleA Dashboard API",
    version="1.0.0",
    description="개인 투자 대시보드 백엔드 API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth ─────────────────────────────────────────────────────────────
DEMO_USER = {"username": "admin", "password": "triplea123"}


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    if not JWT_AVAILABLE:
        return "demo-token"
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


@app.post("/api/auth/token", response_model=TokenResponse, tags=["auth"])
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username != DEMO_USER["username"] or form_data.password != DEMO_USER["password"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증 실패")
    token = create_access_token(
        {"sub": form_data.username},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return TokenResponse(access_token=token)


# ── Dashboard Summary ────────────────────────────────────────────────
@app.get("/api/modes", response_model=List[ModeInfo], tags=["system"])
def list_modes():
    return [provider.mode_info() for provider in provider_router.list()]


@app.get("/api/modes/{mode}", response_model=ModeInfo, tags=["system"])
def get_mode(mode: str):
    return _mode_info(_parse_mode(mode))


@app.post("/api/providers/{mode}/sync-accounts", response_model=ProviderSyncResult, tags=["system"])
def sync_provider_accounts(mode: str):
    provider = provider_router.get(_parse_mode(mode))
    try:
        with get_conn() as conn:
            return provider.sync_accounts(conn)
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e)) from e
    except KISConfigError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except KISAPIError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.get("/api/dashboard/summary", response_model=DashboardSummary, tags=["dashboard"])
def dashboard_summary(mode: Optional[str] = None):
    trading_mode = _parse_mode(mode)
    provider = provider_router.get(trading_mode)
    with get_conn() as conn:
        macro      = get_macro_indicators(conn)
        kpi        = get_kpi_summary(conn, macro)
        targets    = provider.get_target_deviations(conn)
        alerts     = get_recent_alerts(conn)
        calendar   = get_calendar_events(conn)
        accounts   = provider.get_accounts(conn)
        allocation = provider.get_allocation(conn)
        top_movers = provider.get_top_movers(conn)

    suggestions = get_rebalancing_suggestions(targets)
    insights    = build_insights(macro, kpi)

    return DashboardSummary(
        mode=trading_mode,
        modeInfo=_mode_info(trading_mode),
        kpi=kpi,
        macro=macro,
        accounts=accounts,
        allocation=allocation,
        targets=targets,
        suggestions=suggestions,
        topMovers=top_movers,
        calendar=calendar,
        alerts=alerts,
        insights=insights,
    )


# ── Macro ────────────────────────────────────────────────────────────
@app.get("/api/macro/summary", response_model=List[MacroIndicator], tags=["macro"])
def macro_summary():
    with get_conn() as conn:
        return get_macro_indicators(conn)


@app.get("/api/macro/history/{indicator}", tags=["macro"])
def macro_history(indicator: str, days: int = 30):
    """지표 히스토리 반환. days 기준으로 최근 N일치 (오름차순)"""
    from datetime import date, timedelta as td
    start = (date.today() - td(days=days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT date, value FROM indicators
            WHERE indicator = ? AND date >= ?
            ORDER BY date ASC
        """, (indicator, start)).fetchall()
    return [{"date": r["date"], "value": r["value"]} for r in rows]


@app.get("/api/indicators/{key}/history", tags=["macro"])
def indicator_history(key: str, days: int = 180):
    """차트용 지표 히스토리 (alias)"""
    from datetime import date, timedelta as td
    start = (date.today() - td(days=days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT date, value FROM indicators
            WHERE indicator = ? AND date >= ?
            ORDER BY date ASC
        """, (key, start)).fetchall()
    return [{"date": r["date"], "value": r["value"]} for r in rows]


# ── Accounts ─────────────────────────────────────────────────────────
@app.get("/api/accounts", response_model=List[AccountSummary], tags=["accounts"])
def list_accounts(mode: Optional[str] = None):
    provider = provider_router.get(_parse_mode(mode))
    with get_conn() as conn:
        return provider.get_accounts(conn)


@app.get("/api/account-policies", response_model=List[AccountPolicyItem], tags=["accounts"])
def account_policies():
    with get_conn() as conn:
        return get_account_policies(conn)


@app.get("/api/accounts/{account_id}/positions", tags=["accounts"])
def get_positions(account_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM holdings WHERE account_id=? ORDER BY market_value DESC",
            (account_id,)
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/accounts/{account_id}/snapshots", response_model=List[AccountSnapshotItem], tags=["accounts"])
def list_account_snapshots(account_id: int, limit: int = 20):
    with get_conn() as conn:
        return get_account_snapshots(conn, account_id, limit=limit)


@app.post("/api/accounts/{account_id}/manual-snapshot", response_model=AccountSnapshotItem, tags=["accounts"])
def create_manual_snapshot(account_id: int, body: AccountSnapshotCreate, mode: Optional[str] = None):
    trading_mode = _parse_mode(mode)
    _ensure_user_write_mode(trading_mode)
    with get_conn() as conn:
        try:
            return save_manual_snapshot(conn, account_id, body)
        except KeyError:
            raise HTTPException(status_code=404, detail="계좌를 찾을 수 없습니다")


@app.patch("/api/accounts/{account_id}/rebalancing-inclusion", tags=["accounts"])
def update_rebalancing_inclusion(account_id: int, include: bool, mode: Optional[str] = None):
    trading_mode = _parse_mode(mode)
    _ensure_user_write_mode(trading_mode)
    with get_conn() as conn:
        updated = set_account_rebalancing_inclusion(conn, account_id, include)
    if not updated:
        raise HTTPException(status_code=404, detail="계좌를 찾을 수 없습니다")
    return {"ok": True, "account_id": account_id, "include": include}


@app.post("/api/accounts/upload-csv", tags=["accounts"])
async def upload_csv(file: UploadFile = File(...), mode: Optional[str] = None):
    """
    CSV 형식: account_name, ticker, name, quantity, avg_price, current_price
    account_name이 없으면 기본 계좌 "업로드 계좌"를 사용
    """
    trading_mode = _parse_mode(mode)
    _ensure_user_write_mode(trading_mode)

    content = await file.read()
    text = content.decode("utf-8-sig")  # BOM 제거
    reader = csv.DictReader(io.StringIO(text))

    expected_fields = {"ticker", "name", "quantity", "avg_price", "current_price"}
    if not reader.fieldnames or not expected_fields.issubset(set(reader.fieldnames)):
        raise HTTPException(
            status_code=400,
            detail=f"CSV 필드 누락. 필수: {expected_fields}"
        )

    inserted = 0
    with get_conn() as conn:
        for row in reader:
            acct_name = row.get("account_name", "업로드 계좌").strip()
            # 계좌 upsert
            existing = conn.execute(
                "SELECT id FROM accounts WHERE name=?", (acct_name,)
            ).fetchone()
            if existing:
                account_id = existing["id"]
            else:
                cur = conn.execute(
                    """
                    INSERT INTO accounts
                    (name, type, account_type, connection_status, data_source)
                    VALUES (?, '일반', 'GENERAL', 'UNLINKED', 'CSV')
                    """,
                    (acct_name,)
                )
                account_id = cur.lastrowid

            ticker = row["ticker"].strip()
            qty = float(row["quantity"])
            avg_p = float(row["avg_price"])
            cur_p = float(row["current_price"])
            market_value = qty * cur_p
            profit = (cur_p - avg_p) * qty

            # holdings upsert
            existing_h = conn.execute(
                "SELECT id FROM holdings WHERE account_id=? AND ticker=?",
                (account_id, ticker)
            ).fetchone()
            if existing_h:
                conn.execute("""
                    UPDATE holdings SET quantity=?, avg_price=?, current_price=?,
                    market_value=?, profit=?, updated_at=datetime('now','localtime')
                    WHERE id=?
                """, (qty, avg_p, cur_p, market_value, profit, existing_h["id"]))
            else:
                conn.execute("""
                    INSERT INTO holdings
                    (account_id, ticker, name, quantity, avg_price, current_price, market_value, profit)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (account_id, ticker, row["name"].strip(), qty, avg_p, cur_p, market_value, profit))
            inserted += 1
        conn.commit()

    return {"ok": True, "inserted": inserted}


@app.get("/api/allocation", response_model=List[AllocationItem], tags=["accounts"])
def get_allocation():
    with get_conn() as conn:
        return get_allocation_from_holdings(conn)


# ── Targets ──────────────────────────────────────────────────────────
@app.get("/api/targets", response_model=List[TargetItem], tags=["targets"])
def get_targets(mode: Optional[str] = None):
    provider = provider_router.get(_parse_mode(mode))
    with get_conn() as conn:
        return provider.get_target_deviations(conn)


@app.put("/api/targets", tags=["targets"])
def update_target(body: TargetUpdate):
    with get_conn() as conn:
        conn.execute("""
            UPDATE targets
            SET target_value=?, warning_thr=?, danger_thr=?,
                updated_at=datetime('now','localtime')
            WHERE asset_class=?
        """, (body.target_value, body.warning_thr, body.danger_thr, body.asset_class))
        conn.commit()
    return {"ok": True}


# ── Rebalancing ──────────────────────────────────────────────────────
@app.get("/api/rebalancing/suggestions", response_model=List[SuggestionItem], tags=["rebalancing"])
def rebalancing_suggestions(mode: Optional[str] = None):
    provider = provider_router.get(_parse_mode(mode))
    with get_conn() as conn:
        targets = provider.get_target_deviations(conn)
    return get_rebalancing_suggestions(targets)


@app.post("/api/rebalancing/run", response_model=RebalanceRunResponse, tags=["rebalancing"])
def run_rebalancing(mode: Optional[str] = None):
    trading_mode = _parse_mode(mode)
    provider = provider_router.get(trading_mode)
    _ensure_user_write_mode(trading_mode)
    with get_conn() as conn:
        macro = get_macro_indicators(conn)
        kpi = get_kpi_summary(conn, macro)
        targets = provider.get_target_deviations(conn)
        run_id, rows = record_rebalance_results(conn, trading_mode, targets, kpi.totalAssets)
    return RebalanceRunResponse(
        ok=True,
        mode=trading_mode,
        runId=run_id,
        saved=len(rows),
        results=rows,
    )


@app.get("/api/rebalancing/results", response_model=List[RebalanceResultItem], tags=["rebalancing"])
def list_rebalance_results(mode: Optional[str] = None, limit: int = 50):
    trading_mode = _parse_mode(mode) if mode else None
    with get_conn() as conn:
        return get_rebalance_results(conn, trading_mode, limit=limit)


# ── Alerts ───────────────────────────────────────────────────────────
@app.get("/api/alerts/recent", response_model=List[AlertItem], tags=["alerts"])
def recent_alerts(limit: int = 10):
    with get_conn() as conn:
        return get_recent_alerts(conn, limit)


@app.patch("/api/alerts/{alert_id}/read", tags=["alerts"])
def mark_alert_read(alert_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE dashboard_alerts SET is_read=1 WHERE id=?", (alert_id,))
        conn.commit()
    return {"ok": True}


@app.post("/api/alerts/generate", tags=["alerts"])
def generate_alerts():
    """목표 이탈 알림 수동 갱신"""
    with get_conn() as conn:
        n = generate_target_alerts(conn)
    return {"ok": True, "created": n}


# ── Calendar ─────────────────────────────────────────────────────────
@app.get("/api/calendar/events", response_model=List[CalendarEvent], tags=["calendar"])
def calendar_events(from_date: Optional[str] = None, to_date: Optional[str] = None):
    with get_conn() as conn:
        return get_calendar_events(conn, from_date=from_date, to_date=to_date)


# ── Documents ────────────────────────────────────────────────────────
@app.get("/api/documents", response_model=List[DocumentItem], tags=["documents"])
def list_documents(type: Optional[str] = None, limit: int = 100):
    with get_conn() as conn:
        if type and type != "all":
            rows = conn.execute(
                "SELECT * FROM documents WHERE type=? ORDER BY created_at DESC LIMIT ?",
                (type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [DocumentItem(**dict(r)) for r in rows]


@app.get("/api/documents/counts", tags=["documents"])
def document_counts():
    """문서 유형별 카운트"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT type, COUNT(*) as cnt FROM documents GROUP BY type"
        ).fetchall()
    return {r["type"]: r["cnt"] for r in rows}


@app.post("/api/documents", response_model=DocumentItem, tags=["documents"])
def create_document(doc: DocumentItem):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO documents (type, title, content, tags, url) VALUES (?,?,?,?,?)",
            (doc.type, doc.title, doc.content, doc.tags, doc.url),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM documents WHERE id=?", (cur.lastrowid,)).fetchone()
    return DocumentItem(**dict(row))


@app.put("/api/documents/{doc_id}", response_model=DocumentItem, tags=["documents"])
def update_document(doc_id: int, doc: DocumentItem):
    with get_conn() as conn:
        existing = conn.execute("SELECT id FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다")
        conn.execute(
            """UPDATE documents
               SET type=?, title=?, content=?, tags=?, url=?,
                   updated_at=datetime('now','localtime')
               WHERE id=?""",
            (doc.type, doc.title, doc.content, doc.tags, doc.url, doc_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    return DocumentItem(**dict(row))


@app.delete("/api/documents/{doc_id}", tags=["documents"])
def delete_document(doc_id: int):
    with get_conn() as conn:
        existing = conn.execute("SELECT id FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다")
        conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        conn.commit()
    return {"ok": True, "deleted": doc_id}


# ── Health ───────────────────────────────────────────────────────────
@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ── Search ───────────────────────────────────────────────────────────
@app.get("/api/search", tags=["system"])
def search(q: str = ""):
    """글로벌 검색: 매크로 지표, 자료실, 알림"""
    if not q or len(q) < 1:
        return {"results": []}
    q_lower = q.lower()
    results = []
    with get_conn() as conn:
        # 매크로 지표
        rows = conn.execute("""
            SELECT indicator, unit FROM indicators
            WHERE lower(indicator) LIKE ? GROUP BY indicator LIMIT 5
        """, (f"%{q_lower}%",)).fetchall()
        for r in rows:
            results.append({"type": "macro", "key": r["indicator"], "title": r["indicator"], "url": "/macro"})

        # 자료실
        rows = conn.execute("""
            SELECT id, title, type FROM documents
            WHERE lower(title) LIKE ? OR lower(tags) LIKE ? LIMIT 5
        """, (f"%{q_lower}%", f"%{q_lower}%")).fetchall()
        for r in rows:
            results.append({"type": "document", "key": str(r["id"]), "title": r["title"], "url": "/documents"})

        # 알림
        rows = conn.execute("""
            SELECT id, title FROM dashboard_alerts
            WHERE lower(title) LIKE ? LIMIT 3
        """, (f"%{q_lower}%",)).fetchall()
        for r in rows:
            results.append({"type": "alert", "key": str(r["id"]), "title": r["title"], "url": "/alerts"})

    return {"results": results[:10]}


@app.get("/api/system/status", tags=["system"])
def system_status():
    """데이터 동기화 상태 및 파이프라인 정보"""
    from datetime import datetime as dt
    with get_conn() as conn:
        # 마지막 지표 수집 시각
        macro_last = conn.execute(
            "SELECT MAX(created_at) as t FROM indicators"
        ).fetchone()["t"]

        # 총 지표 수 및 최근 7일 수집 건수
        total_rows = conn.execute("SELECT COUNT(*) as c FROM indicators").fetchone()["c"]
        recent_rows = conn.execute("""
            SELECT COUNT(*) as c FROM indicators
            WHERE date >= date('now', '-7 days', 'localtime')
        """).fetchone()["c"]

        # 계좌 CSV 마지막 업로드 시각 (holdings updated_at 최대)
        holdings_last = conn.execute(
            "SELECT MAX(updated_at) as t FROM holdings"
        ).fetchone()["t"]

        # 미읽은 알림 수
        unread = conn.execute(
            "SELECT COUNT(*) as c FROM dashboard_alerts WHERE is_read=0"
        ).fetchone()["c"]

    # 수집 성공률 (7일 데이터가 있으면 정상)
    success_rate = min(99.9, (recent_rows / 50) * 100) if recent_rows > 0 else 0.0

    return {
        "macro_last_update": macro_last,
        "holdings_last_update": holdings_last,
        "total_indicators": total_rows,
        "recent_7d_rows": recent_rows,
        "success_rate": round(success_rate, 1),
        "unread_alerts": unread,
        "pipeline_status": "정상" if recent_rows > 0 else "미확인",
        "timestamp": dt.now().isoformat(),
    }


# ── Telegram 알림 전송 ────────────────────────────────────────────────
@app.post("/api/alerts/notify/telegram", tags=["alerts"])
def notify_telegram(level_filter: str = "danger"):
    """
    미읽은 알림을 Telegram으로 전송합니다.
    level_filter: 'danger' | 'warning' | 'all'
    """
    import os, requests as _req
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    tg_chat = os.getenv("TELEGRAM_CHAT_ID", "")

    # API_KEY 파일에서 읽기 (환경변수 없을 경우 fallback)
    if not tg_token:
        key_file = os.path.join(os.path.dirname(__file__), "..", "API_KEY", "TELEGRAM_KEY")
        try:
            with open(key_file) as f:
                lines = f.read().strip().splitlines()
                for line in lines:
                    if line.startswith("BOT_TOKEN="):
                        tg_token = line.split("=", 1)[1].strip()
                    elif line.startswith("CHAT_ID="):
                        tg_chat = line.split("=", 1)[1].strip()
        except Exception:
            pass

    if not tg_token or not tg_chat:
        raise HTTPException(
            status_code=503,
            detail="Telegram 설정 미완료 (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)"
        )

    with get_conn() as conn:
        if level_filter == "all":
            rows = conn.execute(
                "SELECT * FROM dashboard_alerts WHERE is_read=0 ORDER BY created_at DESC LIMIT 20"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM dashboard_alerts WHERE is_read=0 AND level=? ORDER BY created_at DESC LIMIT 20",
                (level_filter,)
            ).fetchall()

    if not rows:
        return {"ok": True, "sent": 0, "message": "전송할 알림 없음"}

    level_emoji = {"danger": "🔴", "warning": "🟡", "info": "🔵"}
    lines = ["*TripleA 대시보드 알림*\n"]
    for r in rows:
        emoji = level_emoji.get(r["level"], "⚪")
        lines.append(f"{emoji} *{r['title']}*")
        if r["message"]:
            lines.append(f"  {r['message']}")
        lines.append("")

    text = "\n".join(lines).strip()

    try:
        res = _req.post(
            f"https://api.telegram.org/bot{tg_token}/sendMessage",
            json={"chat_id": tg_chat, "text": text, "parse_mode": "Markdown"},
            timeout=15,
        )
        res.raise_for_status()
        return {"ok": True, "sent": len(rows)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Telegram 전송 실패: {str(e)}")
