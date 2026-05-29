from __future__ import annotations

from typing import Any

from api.features.data_status.ports import IDataStatusRepository


class DataStatusService:
    def __init__(self, repo: IDataStatusRepository) -> None:
        self._repo = repo

    def get_status(self) -> Any:
        return self._repo.get_status()

    def get_dataset_status(self, dataset_key: str) -> Any:
        return self._repo.get_dataset_status(dataset_key)

    def get_latest_quotes(self, symbols: list[str], *, market: str = "KRX") -> Any:
        return self._repo.get_latest_quotes(symbols, market=market)
