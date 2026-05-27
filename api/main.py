"""
api/main.py
FastAPI 대시보드 API 서버
실행: cd /Users/bumsangkim/Dev/TripleA && uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
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
    RebalanceResultItem, RebalanceRunResponse, RiskBudgetItem, ProviderSyncResult,
    OrderDraftRequest, OrderDraftResponse, OrderExecuteRequest,
    BacktestRunRequest, BacktestRunResponse, BacktestDecision, BacktestPosition, BacktestTrade,
    AssetUniverseItem, MarketDataCoverageResponse, AssetCoverageItem, FxCoverageItem,
)
from .kis import KISAPIError, KISConfigError, KISNetworkError
from .modes import TradingMode, normalize_mode
from .providers import provider_router
from .market_data_service import (
    get_asset_universe,
    validate_market_data_coverage,
    AssetUniverseItem as _AssetUniverseItem,
)
from .macro_telegram_report import send_daily_macro_report
from .services import (
    get_macro_indicators, get_rebalancing_suggestions,
    get_recent_alerts, get_kpi_summary,
    get_calendar_events, build_insights, generate_target_alerts,
    get_account_policies, save_manual_snapshot,
    get_account_snapshots, set_account_rebalancing_inclusion,
    record_rebalance_results, get_rebalance_results,
    create_order_draft, approve_order_draft, list_order_drafts,
    run_backtest, list_backtest_runs, get_backtest_run,
    get_backtest_decisions, get_backtest_positions, get_backtest_trades,
    get_risk_budget_items, get_indicator_history,
)
from .telegram_service import TelegramConfigError, TelegramSendError, send_telegram_message
from .data.status_service import get_data_status, get_dataset_status, get_latest_quotes_status
from .intraday.router import router as intraday_router
from .strategy_config import (
    list_risk_profiles,
    list_universe_ids,
    load_investment_universe,
    load_sector_taxonomy,
    load_strategy_profile,
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


def _provider_error_detail(code: str, message: str, user_action: str) -> dict[str, str]:
    return {
        "code": code,
        "message": message,
        "userAction": user_action,
    }

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

_cors_raw = os.getenv("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()] or [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(intraday_router)


# ── Auth ─────────────────────────────────────────────────────────────
DEMO_USER = {
    "username": os.getenv("DEMO_USERNAME", "admin"),
    "password": os.getenv("DEMO_PASSWORD", "triplea123"),
}


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    if not JWT_AVAILABLE:
        return "demo-token"
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
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
        logger.info("KIS provider sync config error: %s", e)
        raise HTTPException(
            status_code=503,
            detail=_provider_error_detail(
                "KIS_CONFIG_MISSING",
                "KIS 계좌 동기화 설정이 누락되었습니다.",
                ".env의 KIS 앱키, 시크릿, 계좌번호 설정을 확인하세요.",
            ),
        ) from e
    except KISNetworkError as e:
        logger.warning("KIS provider sync network error: %s", e)
        raise HTTPException(
            status_code=504,
            detail=_provider_error_detail(
                "KIS_NETWORK_ERROR",
                "KIS 서버와 통신하지 못했습니다.",
                "네트워크 상태와 KIS 모의투자 서버 접속 가능 여부를 확인한 뒤 다시 시도하세요.",
            ),
        ) from e
    except KISAPIError as e:
        logger.warning("KIS provider sync API error: %s", e)
        raise HTTPException(
            status_code=502,
            detail=_provider_error_detail(
                "KIS_API_ERROR",
                "KIS API 응답을 처리하지 못했습니다.",
                "KIS OpenAPI 신청 상태, 모의투자 계좌 상태, TR 권한을 확인하세요.",
            ),
        ) from e


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
    with get_conn() as conn:
        return get_indicator_history(conn, indicator, days)


@app.get("/api/indicators/{key}/history", tags=["macro"])
def indicator_history(key: str, days: int = 180):
    """차트용 지표 히스토리 (alias)"""
    with get_conn() as conn:
        return get_indicator_history(conn, key, days)


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


@app.get("/api/engine/risk-budget", response_model=List[RiskBudgetItem], tags=["engine"])
def risk_budget():
    with get_conn() as conn:
        return get_risk_budget_items(conn)


# ── Backtests ───────────────────────────────────────────────────────
@app.post("/api/backtests/run", response_model=BacktestRunResponse, tags=["backtests"])
def run_backtest_endpoint(body: BacktestRunRequest):
    try:
        with get_conn() as conn:
            return run_backtest(conn, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/backtests/runs", response_model=List[BacktestRunResponse], tags=["backtests"])
def backtest_runs(limit: int = 20):
    with get_conn() as conn:
        return list_backtest_runs(conn, limit=limit)


@app.get("/api/backtests/runs/{run_id}", response_model=BacktestRunResponse, tags=["backtests"])
def backtest_run(run_id: int):
    try:
        with get_conn() as conn:
            return get_backtest_run(conn, run_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/api/backtests/runs/{run_id}/decisions", response_model=List[BacktestDecision], tags=["backtests"])
def backtest_decisions(run_id: int):
    try:
        with get_conn() as conn:
            return get_backtest_decisions(conn, run_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/api/backtests/runs/{run_id}/positions", response_model=List[BacktestPosition], tags=["backtests"])
def backtest_positions(run_id: int):
    try:
        with get_conn() as conn:
            return get_backtest_positions(conn, run_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.get("/api/backtests/runs/{run_id}/trades", response_model=List[BacktestTrade], tags=["backtests"])
def backtest_trades(run_id: int):
    try:
        with get_conn() as conn:
            return get_backtest_trades(conn, run_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ── Strategy Metadata ────────────────────────────────────────────────
@app.get("/api/strategy/universes", tags=["strategy"])
def strategy_universes():
    return {
        universe_id: load_investment_universe(universe_id)
        for universe_id in list_universe_ids()
    }


@app.get("/api/strategy/profiles", tags=["strategy"])
def strategy_profiles():
    return {
        profile_id: load_strategy_profile(profile_id)
        for profile_id in list_risk_profiles()
    }


@app.get("/api/strategy/sector-taxonomy", tags=["strategy"])
def strategy_sector_taxonomy():
    return load_sector_taxonomy()


# ── Market Data ──────────────────────────────────────────────────────
@app.get("/api/market-data/assets", response_model=List[AssetUniverseItem], tags=["market-data"])
def market_data_assets(active_only: bool = True):
    with get_conn() as conn:
        items: list[_AssetUniverseItem] = get_asset_universe(conn, active_only=active_only)
    return [
        AssetUniverseItem(
            assetCode=item.asset_code,
            symbol=item.symbol,
            name=item.name,
            assetClass=item.asset_class,
            market=item.market,
            currency=item.currency,
            sourceType=item.source_type,
            isActive=item.is_active,
        )
        for item in items
    ]


@app.get("/api/market-data/coverage", response_model=MarketDataCoverageResponse, tags=["market-data"])
def market_data_coverage(start_date: str, end_date: str):
    from datetime import date as _date
    try:
        start = _date.fromisoformat(start_date)
        end = _date.fromisoformat(end_date)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"날짜 형식 오류: {e}") from e
    if start > end:
        raise HTTPException(status_code=422, detail="start_date는 end_date보다 앞이어야 합니다.")
    with get_conn() as conn:
        universe = get_asset_universe(conn, active_only=True)
        asset_codes = [item.asset_code for item in universe]
        coverage = validate_market_data_coverage(conn, asset_codes, start, end)
    return MarketDataCoverageResponse(
        ok=coverage.ok,
        assets=[
            AssetCoverageItem(
                assetCode=a.asset_code,
                currency=a.currency,
                priceStartDate=a.price_start_date.isoformat() if a.price_start_date else None,
                priceEndDate=a.price_end_date.isoformat() if a.price_end_date else None,
                pricePoints=a.price_points,
                ok=a.ok,
                message=a.message,
            )
            for a in coverage.assets
        ],
        fxRates=[
            FxCoverageItem(
                baseCurrency=f.base_currency,
                quoteCurrency=f.quote_currency,
                rateStartDate=f.rate_start_date.isoformat() if f.rate_start_date else None,
                rateEndDate=f.rate_end_date.isoformat() if f.rate_end_date else None,
                ratePoints=f.rate_points,
                ok=f.ok,
                message=f.message,
            )
            for f in coverage.fx_rates
        ],
        missingMessages=coverage.missing_messages,
    )


@app.get("/api/data/status", tags=["data"])
def data_status():
    with get_conn() as conn:
        return get_data_status(conn)


@app.get("/api/data/status/{dataset_key:path}", tags=["data"])
def data_status_detail(dataset_key: str):
    with get_conn() as conn:
        return get_dataset_status(conn, dataset_key)


@app.get("/api/data/quotes/latest", tags=["data"])
def data_latest_quotes(symbols: str, market: str = "KRX"):
    symbol_list = [symbol.strip() for symbol in symbols.split(",") if symbol.strip()]
    with get_conn() as conn:
        return get_latest_quotes_status(conn, symbol_list, market=market)


# ── Orders ──────────────────────────────────────────────────────────
@app.get("/api/orders/drafts", response_model=List[OrderDraftResponse], tags=["orders"])
def order_drafts(mode: Optional[str] = None, limit: int = 20):
    trading_mode = _parse_mode(mode) if mode else None
    with get_conn() as conn:
        return list_order_drafts(conn, trading_mode, limit=limit)


@app.post("/api/orders/draft", response_model=OrderDraftResponse, tags=["orders"])
def draft_orders(body: OrderDraftRequest):
    try:
        with get_conn() as conn:
            return create_order_draft(
                conn,
                body.mode,
                source=body.source,
                max_order_amount=body.maxOrderAmount,
            )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/orders/execute", response_model=OrderDraftResponse, tags=["orders"])
def execute_order_draft(body: OrderExecuteRequest):
    try:
        with get_conn() as conn:
            return approve_order_draft(
                conn,
                body.mode,
                body.orderDraftId,
                confirm_text=body.confirmText,
            )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


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
            "SELECT MAX(updated) as t FROM indicators"
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


def _telegram_alert_dedup_key(alert: dict, send_date: str) -> str:
    category = alert.get("category") or "general"
    return f"telegram:{send_date}:{alert.get('level')}:{category}:{alert.get('title')}"


def _pending_telegram_alerts(conn, alerts: list[dict], send_date: str) -> tuple[list[tuple[dict, str]], int]:
    pending: list[tuple[dict, str]] = []
    skipped = 0
    for alert in alerts:
        dedup_key = _telegram_alert_dedup_key(alert, send_date)
        existing = conn.execute("""
            SELECT id FROM notification_logs
            WHERE channel_type='TELEGRAM'
              AND dedup_key=?
              AND status='SENT'
            LIMIT 1
        """, (dedup_key,)).fetchone()
        if existing:
            skipped += 1
        else:
            pending.append((alert, dedup_key))
    return pending, skipped


def _record_telegram_notification_logs(
    conn,
    pending: list[tuple[dict, str]],
    status_value: str,
    error_message: str | None = None,
) -> None:
    conn.executemany("""
        INSERT INTO notification_logs
        (channel_type, alert_type, message, dedup_key, status, sent_at, error_message)
        VALUES ('TELEGRAM', ?, ?, ?, ?, datetime('now','localtime'), ?)
    """, [
        (
            alert.get("level"),
            f"{alert.get('title')}\n{alert.get('message') or ''}".strip(),
            dedup_key,
            status_value,
            error_message,
        )
        for alert, dedup_key in pending
    ])
    conn.commit()


# ── Telegram 알림 전송 ────────────────────────────────────────────────
@app.post("/api/alerts/notify/telegram", tags=["alerts"])
def notify_telegram(level_filter: str = "danger"):
    """
    미읽은 알림을 Telegram으로 전송합니다.
    level_filter: 'danger' | 'warning' | 'all'
    """
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
        send_date = conn.execute("SELECT date('now','localtime')").fetchone()[0]
        alerts = [dict(r) for r in rows]
        pending, skipped = _pending_telegram_alerts(conn, alerts, send_date)

    if not alerts:
        return {"ok": True, "sent": 0, "message": "전송할 알림 없음"}
    if not pending:
        return {
            "ok": True,
            "sent": 0,
            "skipped": skipped,
            "message": "오늘 이미 전송한 알림입니다",
        }

    level_emoji = {"danger": "🔴", "warning": "🟡", "info": "🔵"}
    lines = ["*TripleA 대시보드 알림*\n"]
    for alert, _ in pending:
        emoji = level_emoji.get(alert["level"], "⚪")
        lines.append(f"{emoji} *{alert['title']}*")
        if alert["message"]:
            lines.append(f"  {alert['message']}")
        lines.append("")

    text = "\n".join(lines).strip()

    try:
        send_telegram_message(text, parse_mode="Markdown")
        with get_conn() as conn:
            _record_telegram_notification_logs(conn, pending, "SENT")
        return {"ok": True, "sent": len(pending), "skipped": skipped}
    except TelegramConfigError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except TelegramSendError as e:
        error_message = str(e)
        with get_conn() as conn:
            _record_telegram_notification_logs(conn, pending, "FAILED", error_message=error_message)
        raise HTTPException(status_code=502, detail=f"Telegram 전송 실패: {error_message}")


@app.post("/api/macro/notify/telegram", tags=["macro"])
def notify_macro_telegram(force: bool = False, dry_run: bool = False):
    """현재 매크로 DB와 연동된 금일 경제 현황 요약을 Telegram으로 전송합니다."""
    try:
        with get_conn() as conn:
            result = send_daily_macro_report(conn, force=force, dry_run=dry_run)
        return {
            "ok": result.ok,
            "sent": result.sent,
            "skipped": result.skipped,
            "indicatorCount": result.indicator_count,
            "message": result.message,
            "messageId": result.message_id,
            "text": result.text if dry_run else None,
        }
    except TelegramConfigError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except TelegramSendError as e:
        raise HTTPException(status_code=502, detail=f"Telegram 전송 실패: {e}") from e


# ── 설정: API 키 상태 ────────────────────────────────────────────────
_API_KEY_DIR = Path(__file__).resolve().parent.parent / "API_KEY"

_API_KEY_CONFIGS = [
    {"label": "FRED API",       "env": "FRED_API_KEY"},
    {"label": "ECOS API (BOK)", "env": "ECOS_API_KEY"},
    {"label": "KOSIS API",      "env": "KOSIS_API_KEY"},
    {"label": "Telegram Bot",   "env": "TELEGRAM_KEY"},
    {"label": "Naver API",      "env": "NAVER_API_KEY"},
    {"label": "KIS 증권사 API", "env": "KIS_API_KEY"},
    {"label": "FMP API",        "env": "FMP_API_KEY"},
]


@app.get("/api/settings/api-keys", tags=["settings"])
def get_api_keys_status():
    """API_KEY 디렉터리의 키 파일 존재 여부를 반환합니다."""
    result = []
    for k in _API_KEY_CONFIGS:
        file_path = _API_KEY_DIR / k["env"]
        try:
            is_set = file_path.exists() and bool(file_path.read_text(encoding="utf-8").strip())
        except OSError:
            is_set = False
        result.append({"label": k["label"], "env": k["env"], "status": is_set})
    return result
