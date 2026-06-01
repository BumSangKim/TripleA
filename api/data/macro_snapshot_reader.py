from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class MacroSnapshotItem:
    indicator: str
    value: float
    unit: str | None
    data_date: date
    source: str | None


@dataclass(frozen=True)
class MacroSnapshot:
    as_of_date: date
    indicators: dict[str, MacroSnapshotItem]

    def get_value(self, *keys: str) -> float | None:
        normalized = {key.upper() for key in keys}
        for key, item in self.indicators.items():
            if key.upper() in normalized:
                return item.value
        return None


def get_macro_snapshot(conn: sqlite3.Connection, as_of_date: date) -> MacroSnapshot:
    if not _table_exists(conn, "indicators"):
        return MacroSnapshot(as_of_date=as_of_date, indicators={})

    rows = conn.execute(
        """
        SELECT i.indicator, i.value, i.unit, i.date, i.source
        FROM indicators i
        INNER JOIN (
            SELECT indicator, MAX(date) AS max_date
            FROM indicators
            WHERE date <= ?
            GROUP BY indicator
        ) latest
          ON i.indicator = latest.indicator
         AND i.date = latest.max_date
        ORDER BY i.indicator
        """,
        (as_of_date.isoformat(),),
    ).fetchall()
    return MacroSnapshot(
        as_of_date=as_of_date,
        indicators={
            row["indicator"]: MacroSnapshotItem(
                indicator=row["indicator"],
                value=float(row["value"]),
                unit=row["unit"],
                data_date=date.fromisoformat(row["date"][:10]),
                source=row["source"],
            )
            for row in rows
            if row["value"] is not None
        },
    )


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return bool(row)
