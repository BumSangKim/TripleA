from __future__ import annotations

from typing import Any, Protocol


class IHoldingsRepository(Protocol):
    def get_positions(self, account_id: int) -> list[Any]: ...
