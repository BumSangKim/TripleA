from __future__ import annotations

import json
import sqlite3

from api.domain.strategy_inputs import StrategyDecisionLogInput


class SqliteStrategyDecisionLogRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def write_decision_log(
        self,
        payload: StrategyDecisionLogInput,
        *,
        enabled: bool = True,
    ) -> bool:
        if not enabled:
            return False
        self.conn.execute(
            """
            INSERT INTO strategy_decision_logs
            (decision_id, snapshot_id, as_of_date, decision_type, payload_json, reason_codes_json, warnings_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(decision_id) DO UPDATE SET
                payload_json=excluded.payload_json,
                reason_codes_json=excluded.reason_codes_json,
                warnings_json=excluded.warnings_json
            """,
            (
                payload.decision_id,
                payload.snapshot_id,
                payload.as_of_date.isoformat(),
                payload.decision_type,
                json.dumps(payload.payload, sort_keys=True),
                json.dumps(payload.reason_codes, sort_keys=True),
                json.dumps(payload.warnings, sort_keys=True),
            ),
        )
        self.conn.commit()
        return True

