from __future__ import annotations

import sqlite3
from decimal import Decimal

from api.data.repository import (
    ensure_raw_data_tables,
    list_latest_ingestion_runs,
    list_latest_quality,
    read_latest_data_quality,
    read_latest_quote,
)


def get_data_status(conn: sqlite3.Connection) -> dict:
    ensure_raw_data_tables(conn)
    quality_rows = list_latest_quality(db_session=conn)
    runs = list_latest_ingestion_runs(db_session=conn)
    run_by_source = {run["source_id"]: run for run in runs}
    datasets = [_dataset_status(row, run_by_source) for row in quality_rows]
    return {
        "status": "ok" if all(not item["isStale"] for item in datasets) else "degraded",
        "datasets": datasets,
        "lastIngestionRuns": runs[:10],
    }


def get_dataset_status(conn: sqlite3.Connection, dataset_key: str) -> dict:
    ensure_raw_data_tables(conn)
    row = read_latest_data_quality(dataset_key=dataset_key, db_session=conn)
    if not row:
        return {
            "datasetKey": dataset_key,
            "status": "degraded",
            "source": None,
            "latestAsOfDate": None,
            "latestUpdatedAt": None,
            "qualityScore": 0.0,
            "missingRatio": 1.0,
            "isStale": True,
            "lastIngestionStatus": "missing",
            "warnings": ["dataset_not_found"],
        }
    runs = list_latest_ingestion_runs(db_session=conn)
    return _dataset_status(row, {run["source_id"]: run for run in runs})


def get_latest_quotes_status(conn: sqlite3.Connection, symbols: list[str], *, market: str = "KRX") -> dict:
    ensure_raw_data_tables(conn)
    items = []
    for symbol in symbols:
        quote = read_latest_quote(symbol=symbol, market=market, db_session=conn)
        if not quote:
            items.append({"symbol": symbol, "market": market, "status": "missing", "price": None, "source": None})
            continue
        price = quote["price"]
        items.append(
            {
                "symbol": symbol,
                "market": quote["market"],
                "status": "ok" if Decimal(str(price)) > 0 else "degraded",
                "price": str(price),
                "currency": quote["currency"],
                "source": quote["source"],
                "asOfDate": quote["as_of_date"],
                "quoteTime": quote["quote_time"],
            }
        )
    return {"quotes": items}


def _dataset_status(row: dict, runs_by_source: dict[str, dict]) -> dict:
    source_id = _source_id_from_dataset(row["dataset_key"])
    run = runs_by_source.get(source_id)
    return {
        "datasetKey": row["dataset_key"],
        "status": "degraded" if row["is_stale"] or row["quality_score"] < 0.8 else "ok",
        "source": row["source"],
        "latestAsOfDate": row["as_of_date"],
        "latestUpdatedAt": row["updated_at"],
        "qualityScore": row["quality_score"],
        "missingRatio": row["missing_ratio"],
        "isStale": row["is_stale"],
        "lastIngestionStatus": run["status"] if run else "unknown",
        "warnings": row["warnings"],
    }


def _source_id_from_dataset(dataset_key: str) -> str:
    return dataset_key.split(":", 1)[1] if ":" in dataset_key else dataset_key
