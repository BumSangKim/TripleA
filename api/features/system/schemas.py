from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

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
    mode: str
    provider: str
    dbWriteScope: str
    externalApi: bool
    orderPolicy: str
    canWriteUserData: bool
    canExecuteOrders: bool
