from __future__ import annotations

from typing import Any, Protocol


class IMacroRepository(Protocol):
    def get_indicators(self) -> list[Any]: ...
    def get_indicator_history(self, key: str, days: int) -> list[Any]: ...
