from __future__ import annotations

from datetime import date
from typing import Any, Protocol


class IMarketDataRepository(Protocol):
    def get_asset_universe(self, *, active_only: bool = True) -> list[Any]: ...
    def get_coverage(self, asset_codes: list[str], start: date, end: date) -> Any: ...
