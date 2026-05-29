from __future__ import annotations

import sqlite3
from typing import Any


class DataStatusRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_status(self) -> Any:
        from api.data.status_service import get_data_status
        return get_data_status(self._conn)

    def get_dataset_status(self, dataset_key: str) -> Any:
        from api.data.status_service import get_dataset_status
        return get_dataset_status(self._conn, dataset_key)

    def get_latest_quotes(self, symbols: list[str], *, market: str = "KRX") -> Any:
        from api.data.status_service import get_latest_quotes_status
        return get_latest_quotes_status(self._conn, symbols, market=market)
