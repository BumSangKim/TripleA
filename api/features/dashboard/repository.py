from __future__ import annotations

import sqlite3
from typing import Any

from api.features.dashboard.models import DashboardData


class DashboardRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_summary(self, trading_mode: Any) -> DashboardData:
        from api.features.macro.repository import MacroRepository
        from api.features.alerts.repository import AlertsRepository
        from api.features.calendar.repository import CalendarRepository
        from api.features.rebalancing.repository import get_rebalancing_suggestions
        from api.features.accounts.repository import AccountsRepository
        from api.features.targets.repository import TargetsRepository

        macro_repo = MacroRepository(self._conn)
        accounts_repo = AccountsRepository(self._conn)
        targets_repo = TargetsRepository(self._conn)
        macro = macro_repo.get_indicators()
        kpi = macro_repo.get_kpi_summary(macro)
        targets = targets_repo.get_target_deviations(trading_mode)
        alerts = AlertsRepository(self._conn).list_recent(limit=10)
        calendar = CalendarRepository(self._conn).get_events()
        accounts = accounts_repo.get_accounts(trading_mode)
        allocation = accounts_repo.get_allocation()
        top_movers = []
        suggestions = get_rebalancing_suggestions(targets)
        insights = macro_repo.build_insights(macro, kpi)

        return DashboardData(
            mode=trading_mode,
            mode_info={
                "mode": trading_mode,
                "provider": "LocalSimulation",
                "dbWriteScope": "local_manual" if trading_mode == "local" else "results",
                "externalApi": False,
                "orderPolicy": "disabled",
                "canWriteUserData": trading_mode == "local",
                "canExecuteOrders": False,
            },
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
