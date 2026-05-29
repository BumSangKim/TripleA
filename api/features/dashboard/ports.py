from __future__ import annotations

from typing import Any, Protocol


class IDashboardRepository(Protocol):
    def get_summary(self, trading_mode: Any) -> Any: ...
