from __future__ import annotations

import json
import sqlite3

from api.testbed.schema import ensure_testbed_tables


def create_optimization_run(conn: sqlite3.Connection, optimization_run_id: str, search_method: str = "coarse_to_fine") -> str:
    ensure_testbed_tables(conn)
    conn.execute(
        "INSERT INTO optimization_runs (optimization_run_id, search_method, status, summary_json) VALUES (?, ?, 'created', '{}')",
        (optimization_run_id, search_method),
    )
    conn.commit()
    return optimization_run_id


def update_optimization_run_status(conn: sqlite3.Connection, optimization_run_id: str, status: str, summary: dict | None = None) -> None:
    ensure_testbed_tables(conn)
    conn.execute(
        "UPDATE optimization_runs SET status=?, summary_json=?, updated_at=datetime('now','localtime') WHERE optimization_run_id=?",
        (status, json.dumps(summary or {}, sort_keys=True), optimization_run_id),
    )
    conn.commit()


def create_optimization_candidate(conn: sqlite3.Connection, candidate_id: str, optimization_run_id: str, parameter_set_id: str) -> str:
    ensure_testbed_tables(conn)
    conn.execute(
        """
        INSERT INTO optimization_candidates (candidate_id, optimization_run_id, parameter_set_id, status, metrics_json, failure_reasons_json)
        VALUES (?, ?, ?, 'created', '{}', '[]')
        """,
        (candidate_id, optimization_run_id, parameter_set_id),
    )
    conn.commit()
    return candidate_id


def update_optimization_candidate_result(conn: sqlite3.Connection, candidate_id: str, status: str, metrics: dict, failure_reasons: list[str]) -> None:
    ensure_testbed_tables(conn)
    conn.execute(
        """
        UPDATE optimization_candidates
        SET status=?, metrics_json=?, failure_reasons_json=?, updated_at=datetime('now','localtime')
        WHERE candidate_id=?
        """,
        (status, json.dumps(metrics, sort_keys=True), json.dumps(failure_reasons, sort_keys=True), candidate_id),
    )
    conn.commit()


def list_candidates_for_run(conn: sqlite3.Connection, optimization_run_id: str) -> list[dict]:
    ensure_testbed_tables(conn)
    rows = conn.execute("SELECT * FROM optimization_candidates WHERE optimization_run_id=? ORDER BY candidate_id", (optimization_run_id,)).fetchall()
    result = []
    for row in rows:
        data = dict(row)
        data["metrics"] = json.loads(data.pop("metrics_json") or "{}")
        data["failure_reasons"] = json.loads(data.pop("failure_reasons_json") or "[]")
        result.append(data)
    return result
