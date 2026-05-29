from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from api.providers.modes import TradingMode


class HealthResponse(BaseModel):
    status: str
    timestamp: str


class SystemStatusResponse(BaseModel):
    macro_last_update: Optional[str]
    holdings_last_update: Optional[str]
    total_indicators: int
    recent_7d_rows: int
    success_rate: float
    unread_alerts: int
    pipeline_status: str
    timestamp: str


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
