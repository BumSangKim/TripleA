from __future__ import annotations

import json
import sqlite3

from api.testbed.schema import ensure_testbed_tables


def store_score(
    conn: sqlite3.Connection,
    *,
    snapshot_id: str,
    entity_type: str,
    entity_id: str,
    score_name: str,
    score_value: float,
    confidence: float,
    data_quality: float,
    reason_codes: list[str] | None = None,
) -> None:
    ensure_testbed_tables(conn)
    conn.execute(
        """
        INSERT INTO score_store (snapshot_id, entity_type, entity_id, score_name, score_value, confidence, data_quality, reason_codes_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(snapshot_id, entity_type, entity_id, score_name) DO UPDATE SET
            score_value=excluded.score_value,
            confidence=excluded.confidence,
            data_quality=excluded.data_quality,
            reason_codes_json=excluded.reason_codes_json
        """,
        (
            snapshot_id,
            entity_type,
            entity_id,
            score_name,
            score_value,
            confidence,
            data_quality,
            json.dumps(reason_codes or [], sort_keys=True),
        ),
    )
    conn.commit()
