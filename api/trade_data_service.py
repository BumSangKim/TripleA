from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class TradeSeriesItem:
    period: str
    country: str | None
    flow: str
    item_code: str
    item_name: str | None
    amount_usd: float | None
    quantity: float | None
    unit: str | None
    yoy: float | None
    mom: float | None
    source: str | None
    release_date: date


@dataclass(frozen=True)
class TradeSnapshot:
    as_of_date: date
    lookback_months: int
    items: list[TradeSeriesItem]


def get_trade_snapshot(
    conn: sqlite3.Connection,
    as_of_date: date,
    *,
    lookback_months: int = 60,
) -> TradeSnapshot:
    if not _table_exists(conn, "trade_series"):
        return TradeSnapshot(as_of_date=as_of_date, lookback_months=lookback_months, items=[])

    start_date = _subtract_months(as_of_date, lookback_months)
    rows = conn.execute(
        """
        SELECT period, country, flow, item_code, item_name, amount_usd,
               quantity, unit, yoy, mom, source, release_date
        FROM trade_series
        WHERE release_date IS NOT NULL
          AND release_date <= ?
          AND release_date >= ?
        ORDER BY release_date ASC, period ASC, item_code ASC
        """,
        (as_of_date.isoformat(), start_date.isoformat()),
    ).fetchall()
    return TradeSnapshot(
        as_of_date=as_of_date,
        lookback_months=lookback_months,
        items=[
            TradeSeriesItem(
                period=row["period"],
                country=row["country"],
                flow=row["flow"],
                item_code=row["item_code"],
                item_name=row["item_name"],
                amount_usd=_optional_float(row["amount_usd"]),
                quantity=_optional_float(row["quantity"]),
                unit=row["unit"],
                yoy=_optional_float(row["yoy"]),
                mom=_optional_float(row["mom"]),
                source=row["source"],
                release_date=date.fromisoformat(row["release_date"][:10]),
            )
            for row in rows
        ],
    )


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return bool(row)


def _subtract_months(value: date, months: int) -> date:
    month_index = value.month - 1 - max(months, 0)
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, _last_day_of_month(year, month))
    return date(year, month, day)


def _last_day_of_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - date(year, month, 1)).days


def _optional_float(value) -> float | None:
    return None if value is None else float(value)
