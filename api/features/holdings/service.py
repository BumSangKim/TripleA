from __future__ import annotations

from typing import Any

from api.features.holdings.ports import IHoldingsRepository


class HoldingsService:
    def __init__(self, repo: IHoldingsRepository) -> None:
        self._repo = repo

    def get_positions(self, account_id: int) -> list[Any]:
        return self._repo.get_positions(account_id)
