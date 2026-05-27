from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime

from api.testbed.schema import ensure_testbed_tables


def create_data_snapshot(conn: sqlite3.Connection, as_of_date: date, source_tables: list[str]) -> dict:
    ensure_testbed_tables(conn)
    snapshot_id = f"snapshot_{as_of_date.isoformat()}_{'_'.join(sorted(source_tables))}"
    payload = {
        "snapshot_id": snapshot_id,
        "as_of_date": as_of_date.isoformat(),
        "source_tables": sorted(source_tables),
        "created_at": datetime.now(UTC).isoformat(),
        "data_cutoff_at": datetime.combine(as_of_date, datetime.max.time(), tzinfo=UTC).isoformat(),
    }
    conn.execute(
        """
        INSERT INTO data_snapshots (snapshot_id, as_of_date, data_cutoff_at, source_tables_json, quality_json)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(snapshot_id) DO UPDATE SET
            source_tables_json=excluded.source_tables_json,
            quality_json=excluded.quality_json
        """,
        (
            payload["snapshot_id"],
            payload["as_of_date"],
            payload["data_cutoff_at"],
            json.dumps(payload["source_tables"], sort_keys=True),
            json.dumps({"status": "created"}, sort_keys=True),
        ),
    )
    conn.commit()
    return payload


def get_data_snapshot(conn: sqlite3.Connection, snapshot_id: str) -> dict | None:
    ensure_testbed_tables(conn)
    row = conn.execute("SELECT * FROM data_snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    data["source_tables"] = json.loads(data.pop("source_tables_json"))
    data["quality"] = json.loads(data.pop("quality_json") or "{}")
    return data


def compute_data_quality(conn: sqlite3.Connection, entity_type: str, entity_id: str, as_of_date: date) -> dict:
    if entity_type == "asset":
        try:
            rows = conn.execute(
                """
                SELECT price_date AS observed_date
                FROM market_prices
                WHERE asset_code=? AND price_date <= ?
                ORDER BY price_date DESC
                LIMIT 252
                """,
                (entity_id, as_of_date.isoformat()),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
    else:
        rows = []
    coverage_ratio = min(len(rows) / 252, 1.0)
    missing_ratio = 1.0 - coverage_ratio
    latest = rows[0]["observed_date"] if rows else None
    is_stale = latest is None or (as_of_date - date.fromisoformat(latest)).days > 7
    quality_score = max(0.0, min(1.0, coverage_ratio - (0.2 if is_stale else 0.0)))
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "as_of_date": as_of_date.isoformat(),
        "quality_score": round(quality_score, 4),
        "missing_ratio": round(missing_ratio, 4),
        "coverage_ratio": round(coverage_ratio, 4),
        "is_stale": is_stale,
        "warnings": ["stale_or_missing"] if is_stale else [],
    }
