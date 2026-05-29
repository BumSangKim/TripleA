from __future__ import annotations

from typing import Any

from api.features.dashboard.models import DashboardData
from api.features.dashboard.ports import IDashboardRepository


class DashboardService:
    def __init__(self, repo: IDashboardRepository) -> None:
        self._repo = repo

    def get_summary(self, trading_mode: Any) -> DashboardData:
        return self._repo.get_summary(trading_mode)
