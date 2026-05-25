"""
api/models.py
Pydantic 스키마 정의
"""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

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


class RiskBudgetItem(BaseModel):
    strategyBucket: str
    currentRatio: float
    targetRatio: float
    minRatio: Optional[float] = None
    maxRatio: Optional[float] = None
    deviation: float
    level: str
    action: str
    reason: str


class ProviderSyncResult(BaseModel):
    ok: bool
    mode: TradingMode
    provider: str
    accountId: Optional[int] = None
    accountMasked: Optional[str] = None
    syncedPositions: int = 0
    totalValue: float = 0
    cashValue: float = 0
    message: Optional[str] = None


# ── Orders ───────────────────────────────────────────────────────────
class OrderDraftRequest(BaseModel):
    mode: TradingMode = TradingMode.PAPER
    source: str = "rebalancing"
    maxOrderAmount: Optional[float] = None


class OrderExecuteRequest(BaseModel):
    mode: TradingMode
    orderDraftId: int
    confirmText: Optional[str] = None


class OrderItem(BaseModel):
    id: Optional[int] = None
    draftId: Optional[int] = None
    accountId: Optional[int] = None
    assetClass: str
    side: str
    amount: float
    status: str
    reason: Optional[str] = None
    createdAt: Optional[str] = None


class OrderDraftResponse(BaseModel):
    ok: bool
    draftId: int
    mode: TradingMode
    source: str
    status: str
    totalAmount: float
    itemCount: int
    items: List[OrderItem]
    message: Optional[str] = None


class BacktestRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "TripleA Dynamic Backtest"
    startDate: str
    endDate: str
    initialCapital: float
    strategyMode: str = "triplea_dynamic"
    riskProfile: str = "balanced"
    universeId: str = "default_global"
    rebalanceFrequency: str = "monthly"
    baseCurrency: str = "KRW"
    feeBps: float = 5.0
    slippageBps: float = 5.0
    taxBps: float = 0.0
    dataLookbackYears: int = 5


class BacktestPoint(BaseModel):
    date: str
    value: float
    drawdown: float


class BacktestPosition(BaseModel):
    date: str
    assetCode: str
    quantity: float
    price: float
    fxRate: float
    marketValue: float
    weight: float


class BacktestTrade(BaseModel):
    date: str
    assetCode: str
    side: str
    quantity: float
    price: float
    fxRate: float
    grossAmount: float
    fee: float = 0
    slippage: float = 0
    tax: float = 0
    netAmount: float
    reason: Optional[str] = None


class BacktestDecision(BaseModel):
    date: str
    strategyMode: str
    riskProfile: Optional[str] = None
    universeId: Optional[str] = None
    macroRegime: Optional[str] = None
    macroScore: Optional[int] = None
    bucketWeights: dict[str, float] = Field(default_factory=dict)
    finalWeights: dict[str, float] = Field(default_factory=dict)
    bottleneckScores: dict[str, float] = Field(default_factory=dict)
    reasons: List[str] = Field(default_factory=list)


class BacktestRunResponse(BaseModel):
    ok: bool
    runId: int
    name: str
    startDate: str
    endDate: str
    initialCapital: float
    strategyMode: str = "triplea_dynamic"
    riskProfile: str = "balanced"
    universeId: str = "default_global"
    rebalanceFrequency: str
    baseCurrency: str = "KRW"
    feeBps: float = 0
    slippageBps: float = 0
    taxBps: float = 0
    dataLookbackYears: int = 5
    status: str
    totalReturn: float
    annualReturn: float
    maxDrawdown: float
    volatility: float
    points: List[BacktestPoint]
    positions: List[BacktestPosition] = Field(default_factory=list)
    trades: List[BacktestTrade] = Field(default_factory=list)
    decisions: List[BacktestDecision] = Field(default_factory=list)
    createdAt: Optional[str] = None


# ── Market Data ──────────────────────────────────────────────────────
class AssetUniverseItem(BaseModel):
    assetCode: str
    symbol: str
    name: Optional[str]
    assetClass: str
    market: Optional[str]
    currency: str
    sourceType: str
    isActive: bool


class AssetCoverageItem(BaseModel):
    assetCode: str
    currency: str
    priceStartDate: Optional[str]
    priceEndDate: Optional[str]
    pricePoints: int
    ok: bool
    message: Optional[str] = None


class FxCoverageItem(BaseModel):
    baseCurrency: str
    quoteCurrency: str
    rateStartDate: Optional[str]
    rateEndDate: Optional[str]
    ratePoints: int
    ok: bool
    message: Optional[str] = None


class MarketDataCoverageResponse(BaseModel):
    ok: bool
    assets: List[AssetCoverageItem]
    fxRates: List[FxCoverageItem]
    missingMessages: List[str]


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
