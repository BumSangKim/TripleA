from __future__ import annotations

from typing import Any

from api.features.strategy.ports import IStrategyRepository


class StrategyService:
    def __init__(self, repo: IStrategyRepository) -> None:
        self._repo = repo

    def get_universes(self) -> dict[str, Any]:
        return self._repo.get_universes()

    def get_profiles(self) -> dict[str, Any]:
        return self._repo.get_profiles()

    def get_sector_taxonomy(self) -> Any:
        return self._repo.get_sector_taxonomy()
