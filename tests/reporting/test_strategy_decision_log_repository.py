from __future__ import annotations

import ast
import json
import sqlite3
from datetime import date
from pathlib import Path

from api.domain.strategy_inputs import StrategyDecisionLogInput
from api.reporting.strategy_decision_log_repository import SqliteStrategyDecisionLogRepository


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE strategy_decision_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_id TEXT NOT NULL UNIQUE,
            snapshot_id TEXT,
            as_of_date TEXT NOT NULL,
            decision_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            reason_codes_json TEXT,
            warnings_json TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
        """
    )
    return conn


def test_strategy_decision_log_repository_writes_existing_schema_row():
    conn = _conn()
    payload = StrategyDecisionLogInput(
        decision_id="d1",
        snapshot_id="s1",
        as_of_date=date(2026, 5, 27),
        decision_type="backtest_allocation",
        payload={"a": 1},
        reason_codes=["ok"],
        warnings=["review"],
    )

    assert SqliteStrategyDecisionLogRepository(conn).write_decision_log(payload) is True

    row = conn.execute("SELECT * FROM strategy_decision_logs WHERE decision_id='d1'").fetchone()
    assert row["snapshot_id"] == "s1"
    assert row["as_of_date"] == "2026-05-27"
    assert json.loads(row["payload_json"]) == {"a": 1}
    assert json.loads(row["reason_codes_json"]) == ["ok"]
    assert json.loads(row["warnings_json"]) == ["review"]


def test_strategy_decision_log_repository_disabled_noops_like_legacy_logger():
    conn = _conn()
    payload = StrategyDecisionLogInput(
        decision_id="d0",
        as_of_date=date(2026, 5, 27),
        decision_type="backtest_allocation",
        payload={},
    )

    assert SqliteStrategyDecisionLogRepository(conn).write_decision_log(payload, enabled=False) is False
    count = conn.execute("SELECT COUNT(*) AS count FROM strategy_decision_logs").fetchone()["count"]
    assert count == 0


def test_strategy_decision_log_repository_updates_reproducible_json_payload():
    conn = _conn()
    repository = SqliteStrategyDecisionLogRepository(conn)
    payload = StrategyDecisionLogInput(
        decision_id="d1",
        as_of_date=date(2026, 5, 27),
        decision_type="backtest_allocation",
        payload={"b": 2, "a": 1},
        reason_codes=["ok"],
    )

    repository.write_decision_log(payload)
    repository.write_decision_log(
        StrategyDecisionLogInput(
            decision_id="d1",
            as_of_date=date(2026, 5, 27),
            decision_type="backtest_allocation",
            payload={"c": 3},
            reason_codes=["updated"],
        )
    )

    row = conn.execute("SELECT * FROM strategy_decision_logs WHERE decision_id='d1'").fetchone()
    assert row["payload_json"] == '{"c": 3}'
    assert json.loads(row["reason_codes_json"]) == ["updated"]


def test_strategy_decision_log_repository_does_not_import_strategy_logger():
    path = Path("api/reporting/strategy_decision_log_repository.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = {"api.strategy.decision_logger"}

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert imports.isdisjoint(forbidden)

