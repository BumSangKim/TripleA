from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class BottleneckIndicatorItem:
    indicator_key: str
    indicator_name: str | None
    sector_code: str
    value_date: date
    release_date: date
    value: float | None
    unit: str | None
    source: str | None
    layer: str | None


@dataclass(frozen=True)
class BottleneckSnapshot:
    as_of_date: date
    lookback_months: int
    indicators: list[BottleneckIndicatorItem]


@dataclass(frozen=True)
class SectorAssetMapping:
    sector_code: str
    asset_code: str
    asset_name: str | None
    asset_type: str | None
    currency: str
    priority: int


def get_bottleneck_snapshot(
    conn: sqlite3.Connection,
    as_of_date: date,
    *,
    lookback_months: int = 60,
) -> BottleneckSnapshot:
    if not _table_exists(conn, "bottleneck_indicators"):
        return BottleneckSnapshot(as_of_date=as_of_date, lookback_months=lookback_months, indicators=[])

    start_date = _subtract_months(as_of_date, lookback_months)
    rows = conn.execute(
        """
        SELECT indicator_key, indicator_name, sector_code, value_date,
               release_date, value, unit, source, layer
        FROM bottleneck_indicators
        WHERE release_date IS NOT NULL
          AND release_date <= ?
          AND release_date >= ?
        ORDER BY release_date ASC, value_date ASC, indicator_key ASC
        """,
        (as_of_date.isoformat(), start_date.isoformat()),
    ).fetchall()
    return BottleneckSnapshot(
        as_of_date=as_of_date,
        lookback_months=lookback_months,
        indicators=[
            BottleneckIndicatorItem(
                indicator_key=row["indicator_key"],
                indicator_name=row["indicator_name"],
                sector_code=row["sector_code"],
                value_date=date.fromisoformat(row["value_date"][:10]),
                release_date=date.fromisoformat(row["release_date"][:10]),
                value=_optional_float(row["value"]),
                unit=row["unit"],
                source=row["source"],
                layer=row["layer"],
            )
            for row in rows
        ],
    )


def get_sector_asset_mappings(conn: sqlite3.Connection) -> dict[str, list[SectorAssetMapping]]:
    if not _table_exists(conn, "sector_asset_map"):
        return {}

    rows = conn.execute(
        """
        SELECT sector_code, asset_code, asset_name, asset_type, currency, priority
        FROM sector_asset_map
        WHERE COALESCE(is_active, 1) = 1
        ORDER BY sector_code ASC, priority ASC, asset_code ASC
        """
    ).fetchall()
    mappings: dict[str, list[SectorAssetMapping]] = {}
    for row in rows:
        mappings.setdefault(row["sector_code"], []).append(
            SectorAssetMapping(
                sector_code=row["sector_code"],
                asset_code=row["asset_code"],
                asset_name=row["asset_name"],
                asset_type=row["asset_type"],
                currency=row["currency"] or "USD",
                priority=int(row["priority"] or 100),
            )
        )
    return mappings


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
