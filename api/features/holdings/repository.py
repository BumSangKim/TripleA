from __future__ import annotations

import sqlite3
from typing import Any


class HoldingsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_positions(self, account_id: int) -> list[Any]:
        rows = self._conn.execute(
            "SELECT * FROM holdings WHERE account_id=? ORDER BY market_value DESC",
            (account_id,),
        ).fetchall()
        return [dict(r) for r in rows]
