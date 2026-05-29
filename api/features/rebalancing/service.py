from __future__ import annotations

from typing import Any, Optional

from api.features.rebalancing.models import RebalanceRunData
from api.features.rebalancing.ports import IRebalancingRepository


class RebalancingService:
    def __init__(self, repo: IRebalancingRepository) -> None:
        self._repo = repo

    def get_suggestions(self, mode: Any) -> list[Any]:
        return self._repo.get_suggestions(mode)

    def run_rebalancing(self, mode: Any) -> RebalanceRunData:
        return self._repo.run_rebalancing(mode)

    def get_results(self, mode: Optional[Any], limit: int) -> list[Any]:
        return self._repo.get_results(mode, limit)

    def get_risk_budget(self) -> list[Any]:
        return self._repo.get_risk_budget()
