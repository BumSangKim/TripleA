from __future__ import annotations

import json
import sqlite3
from datetime import date

from api.testbed.schema import ensure_testbed_tables


def log_strategy_decision(
    conn: sqlite3.Connection,
    *,
    enabled: bool,
    decision_id: str,
    as_of_date: date,
    decision_type: str,
    payload: dict,
    snapshot_id: str | None = None,
    reason_codes: list[str] | None = None,
    warnings: list[str] | None = None,
) -> bool:
    if not enabled:
        return False
    ensure_testbed_tables(conn)
    conn.execute(
        """
        INSERT INTO strategy_decision_logs (decision_id, snapshot_id, as_of_date, decision_type, payload_json, reason_codes_json, warnings_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(decision_id) DO UPDATE SET
            payload_json=excluded.payload_json,
            reason_codes_json=excluded.reason_codes_json,
            warnings_json=excluded.warnings_json
        """,
        (
            decision_id,
            snapshot_id,
            as_of_date.isoformat(),
            decision_type,
            json.dumps(payload, sort_keys=True),
            json.dumps(reason_codes or [], sort_keys=True),
            json.dumps(warnings or [], sort_keys=True),
        ),
    )
    conn.commit()
    return True
