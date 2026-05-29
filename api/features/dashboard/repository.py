from __future__ import annotations

import sqlite3
from typing import Any

from api.features.dashboard.models import DashboardData


class DashboardRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_summary(self, trading_mode: Any) -> DashboardData:
        from api.providers.router import provider_router
        from api.features.macro.repository import MacroRepository
        from api.features.alerts.repository import AlertsRepository
        from api.features.calendar.repository import CalendarRepository
        from api.features.rebalancing.repository import get_rebalancing_suggestions

        provider = provider_router.get(trading_mode)
        macro_repo = MacroRepository(self._conn)
        macro = macro_repo.get_indicators()
        kpi = macro_repo.get_kpi_summary(macro)
        targets = provider.get_target_deviations(self._conn)
        alerts = AlertsRepository(self._conn).list_recent(limit=10)
        calendar = CalendarRepository(self._conn).get_events()
        accounts = provider.get_accounts(self._conn)
        allocation = provider.get_allocation(self._conn)
        top_movers = provider.get_top_movers(self._conn)
        suggestions = get_rebalancing_suggestions(targets)
        insights = macro_repo.build_insights(macro, kpi)

        return DashboardData(
            mode=trading_mode,
            mode_info=provider.mode_info(),
            kpi=kpi,
            macro=macro,
            accounts=accounts,
            allocation=allocation,
            targets=targets,
            suggestions=suggestions,
            top_movers=top_movers,
            calendar=calendar,
            alerts=alerts,
            insights=insights,
        )
