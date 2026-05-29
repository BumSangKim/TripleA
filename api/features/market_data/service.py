from __future__ import annotations

from datetime import date
from typing import Any

from api.features.market_data.ports import IMarketDataRepository


class MarketDataService:
    def __init__(self, repo: IMarketDataRepository) -> None:
        self._repo = repo

    def list_assets(self, *, active_only: bool = True) -> list[Any]:
        return self._repo.get_asset_universe(active_only=active_only)

    def get_coverage(self, start: date, end: date) -> Any:
        universe = self._repo.get_asset_universe(active_only=True)
        asset_codes = [item.asset_code for item in universe]
        return self._repo.get_coverage(asset_codes, start, end)
