from __future__ import annotations

from typing import Any

from api.features.search.ports import ISearchRepository


class SearchService:
    def __init__(self, repo: ISearchRepository) -> None:
        self._repo = repo

    def search(self, q: str) -> list[Any]:
        if not q or len(q) < 1:
            return []
        return self._repo.search(q)
