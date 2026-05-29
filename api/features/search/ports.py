from __future__ import annotations

from typing import Any, Protocol


class ISearchRepository(Protocol):
    def search(self, q: str) -> list[Any]: ...
