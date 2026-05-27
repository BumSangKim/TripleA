from __future__ import annotations

import hashlib
import json
import sqlite3

from api.testbed.schema import ensure_testbed_tables


def create_parameter_set(conn: sqlite3.Connection, parameters: dict, parent_parameter_set_id: str | None = None) -> str:
    ensure_testbed_tables(conn)
    payload = json.dumps(parameters, sort_keys=True)
    parameter_set_id = "param_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    conn.execute(
        """
        INSERT OR IGNORE INTO parameter_sets (parameter_set_id, parent_parameter_set_id, parameters_json)
        VALUES (?, ?, ?)
        """,
        (parameter_set_id, parent_parameter_set_id, payload),
    )
    conn.commit()
    return parameter_set_id


def get_parameter_set(conn: sqlite3.Connection, parameter_set_id: str) -> dict | None:
    ensure_testbed_tables(conn)
    row = conn.execute("SELECT * FROM parameter_sets WHERE parameter_set_id=?", (parameter_set_id,)).fetchone()
    return _parameter_row(row) if row else None


def list_parameter_sets(conn: sqlite3.Connection) -> list[dict]:
    ensure_testbed_tables(conn)
    return [_parameter_row(row) for row in conn.execute("SELECT * FROM parameter_sets ORDER BY created_at").fetchall()]


def _parameter_row(row) -> dict:
    data = dict(row)
    data["parameters"] = json.loads(data.pop("parameters_json"))
    return data
