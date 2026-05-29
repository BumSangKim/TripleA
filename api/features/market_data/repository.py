from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any


class MarketDataRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_asset_universe(self, *, active_only: bool = True) -> list[Any]:
        from api.market_data_service import get_asset_universe
        return get_asset_universe(self._conn, active_only=active_only)

    def get_coverage(self, asset_codes: list[str], start: date, end: date) -> Any:
        from api.market_data_service import validate_market_data_coverage
        return validate_market_data_coverage(self._conn, asset_codes, start, end)
