"""
api/models.py
Pydantic 스키마 정의
"""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel

from .modes import TradingMode


# ── KPI ─────────────────────────────────────────────────────────────
class KPISummary(BaseModel):
    totalAssets: float
    cash: float
    todayProfit: float
    todayProfitRate: float
    riskLevel: str
    macroScore: Optional[int] = None


class ModeInfo(BaseModel):
    mode: TradingMode
    provider: str
    dbWriteScope: str
    externalApi: bool
    orderPolicy: str
    canWriteUserData: bool
    canExecuteOrders: bool


# ── Macro ────────────────────────────────────────────────────────────
class MacroIndicator(BaseModel):
    key: str
    name: str
    value: Optional[float]
    unit: Optional[str]
    change: Optional[float]
    status: str              # rising | falling | stable
    date: Optional[str]
    history: Optional[List[float]] = None


# ── Account ──────────────────────────────────────────────────────────
class AccountSummary(BaseModel):
    id: int
    name: str
    type: Optional[str]
    value: float
    profit: float
    profitRate: float
    accountType: Optional[str] = None
    connectionStatus: Optional[str] = None
    tradeStatus: Optional[str] = None
    includeInRebalancing: bool = True
    dataSource: Optional[str] = None
    lastSyncedAt: Optional[str] = None


class AccountPolicyItem(BaseModel):
    id: int
    accountType: str
    role: str
    depositPolicy: Optional[str] = None
    allowedProducts: Optional[str] = None
    rebalancePriority: Optional[str] = None
    riskNote: Optional[str] = None


class AccountSnapshotCreate(BaseModel):
    totalValue: float
    cashValue: float = 0
    domesticStockValue: float = 0
    foreignStockValue: float = 0
    bondValue: float = 0
    etfValue: float = 0
    pensionValue: float = 0
    altValue: float = 0
    snapshotAt: Optional[str] = None


class AccountSnapshotItem(AccountSnapshotCreate):
    id: int
    accountId: int
    createdAt: Optional[str] = None


class AllocationItem(BaseModel):
    asset: str
    value: float
    ratio: float


# ── Targets / Deviation ──────────────────────────────────────────────
class TargetItem(BaseModel):
    id: Optional[int] = None
    asset_class: str
    target_type: Optional[str] = "asset_allocation"
    currentRatio: float
    targetRatio: float
    deviation: float
    level: str               # normal | warning | danger
    unit: Optional[str] = "%"


class TargetUpdate(BaseModel):
    asset_class: str
    target_value: float
    warning_thr: Optional[float] = 3.0
    danger_thr: Optional[float] = 5.0


# ── Rebalancing ──────────────────────────────────────────────────────
class SuggestionItem(BaseModel):
    asset: str
    action: str              # 비중 축소 | 비중 확대 | 관망
    reason: str
    deviation: float


class RebalanceResultItem(BaseModel):
    id: Optional[int] = None
    runId: Optional[int] = None
    mode: TradingMode
    accountId: Optional[int] = None
    accountType: Optional[str] = None
    assetClass: str
    currentRatio: float
    targetRatio: float
    deviation: float
    action: str
    amount: float
    reason: str
    createdAt: Optional[str] = None


class RebalanceRunResponse(BaseModel):
    ok: bool
    mode: TradingMode
    runId: int
    saved: int
    results: List[RebalanceResultItem]


# ── Top Movers ───────────────────────────────────────────────────────
class TopMover(BaseModel):
    symbol: str
    name: Optional[str]
    price: Optional[float]
    changeRate: float
    contribution: Optional[float]


# ── Calendar ─────────────────────────────────────────────────────────
class CalendarEvent(BaseModel):
    id: Optional[int] = None
    date: str
    time: Optional[str]
    title: str
    country: str
    importance: str          # high | medium | low


# ── Alert ────────────────────────────────────────────────────────────
class AlertItem(BaseModel):
    id: int
    level: str               # info | warning | danger
    category: Optional[str]
    title: str
    message: Optional[str]
    is_read: bool
    created_at: str


# ── Insights ─────────────────────────────────────────────────────────
class Insights(BaseModel):
    macroSummary: str
    portfolioSummary: str
    marketRisk: str
    recommendation: str


# ── Dashboard Summary (통합) ─────────────────────────────────────────
class DashboardSummary(BaseModel):
    mode: TradingMode = TradingMode.TEST
    modeInfo: Optional[ModeInfo] = None
    kpi: KPISummary
    macro: List[MacroIndicator]
    accounts: List[AccountSummary]
    allocation: List[AllocationItem]
    targets: List[TargetItem]
    suggestions: List[SuggestionItem]
    topMovers: List[TopMover]
    calendar: List[CalendarEvent]
    alerts: List[AlertItem]
    insights: Insights


# ── Document ─────────────────────────────────────────────────────────
class DocumentItem(BaseModel):
    id: Optional[int] = None
    type: str = "memo"
    title: str
    content: Optional[str] = None
    tags: Optional[str] = None
    url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ── Auth ─────────────────────────────────────────────────────────────
class TokenRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
