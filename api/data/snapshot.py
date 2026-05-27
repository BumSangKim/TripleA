from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Any

from api.data.repository import ensure_raw_data_tables


@dataclass(frozen=True)
class DataSnapshot:
    snapshot_id: str
    as_of_date: date
    included_datasets: dict[str, list[dict[str, Any]]]
    max_data_date: dict[str, str | None]
    sources: dict[str, list[str]]
    warnings: list[str]


def build_data_snapshot(
    *,
    conn: sqlite3.Connection,
    as_of_date: date,
    dataset_types: list[str],
    symbols: list[str] | None = None,
    indicator_keys: list[str] | None = None,
) -> DataSnapshot:
    ensure_raw_data_tables(conn)
    included: dict[str, list[dict[str, Any]]] = {}
    max_dates: dict[str, str | None] = {}
    sources: dict[str, list[str]] = {}
    warnings: list[str] = []

    if "market_price_daily" in dataset_types:
        rows = _market_rows(conn, as_of_date, symbols or [])
        included["market_price_daily"] = rows
        max_dates["market_price_daily"] = _max_value(rows, "date")
        sources["market_price_daily"] = sorted({row["source"] for row in rows})
        if not rows:
            warnings.append("market_price_daily_empty")

    if "macro_indicator" in dataset_types:
        rows = _macro_rows(conn, as_of_date, indicator_keys or [])
        included["macro_indicator"] = rows
        max_dates["macro_indicator"] = _max_value(rows, "date")
        sources["macro_indicator"] = sorted({row["source"] for row in rows})
        if not rows:
            warnings.append("macro_indicator_empty")

    payload = {
        "as_of_date": as_of_date.isoformat(),
        "dataset_types": sorted(dataset_types),
        "symbols": sorted(symbols or []),
        "indicator_keys": sorted(indicator_keys or []),
        "max_data_date": max_dates,
        "row_counts": {key: len(value) for key, value in included.items()},
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return DataSnapshot(
        snapshot_id=f"data_snapshot_{as_of_date.strftime('%Y%m%d')}_{digest}",
        as_of_date=as_of_date,
        included_datasets=included,
        max_data_date=max_dates,
        sources=sources,
        warnings=warnings,
    )


def _market_rows(conn: sqlite3.Connection, as_of_date: date, symbols: list[str]) -> list[dict[str, Any]]:
    params: list[Any] = [as_of_date.isoformat(), as_of_date.isoformat()]
    symbol_sql = ""
    if symbols:
        symbol_sql = f"AND symbol IN ({','.join('?' for _ in symbols)})"
        params.extend(symbols)
    rows = conn.execute(
        f"""
        SELECT *
        FROM raw_market_prices
        WHERE date <= ?
          AND as_of_date <= ?
          {symbol_sql}
        ORDER BY symbol, date
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def _macro_rows(conn: sqlite3.Connection, as_of_date: date, indicator_keys: list[str]) -> list[dict[str, Any]]:
    params: list[Any] = [as_of_date.isoformat(), as_of_date.isoformat(), as_of_date.isoformat()]
    indicator_sql = ""
    if indicator_keys:
        indicator_sql = f"AND indicator_key IN ({','.join('?' for _ in indicator_keys)})"
        params.extend(indicator_keys)
    rows = conn.execute(
        f"""
        SELECT *
        FROM raw_macro_indicators
        WHERE date <= ?
          AND as_of_date <= ?
          AND (release_date IS NULL OR release_date <= ?)
          {indicator_sql}
        ORDER BY indicator_key, date
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def _max_value(rows: list[dict[str, Any]], key: str) -> str | None:
    values = [row[key] for row in rows if row.get(key)]
    return max(values) if values else None
