from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

from api.features.accounts.schemas import AccountSummary, AllocationItem
from api.features.alerts.schemas import AlertItemSchema
from api.features.calendar.schemas import CalendarEventSchema
from api.features.holdings.schemas import TopMover
from api.features.macro.schemas import MacroIndicator
from api.features.rebalancing.schemas import SuggestionItem
from api.features.system.schemas import KPISummary, ModeInfo
from api.features.targets.schemas import TargetItem


class Insights(BaseModel):
    macroSummary: str
    portfolioSummary: str
    marketRisk: str
    recommendation: str


class DashboardSummarySchema(BaseModel):
    mode: str = "local"
    modeInfo: Optional[ModeInfo] = None
    kpi: KPISummary
    macro: List[MacroIndicator]
    accounts: List[AccountSummary]
    allocation: List[AllocationItem]
    targets: List[TargetItem]
    suggestions: List[SuggestionItem]
    topMovers: List[TopMover]
    calendar: List[CalendarEventSchema]
    alerts: List[AlertItemSchema]
    insights: Insights
