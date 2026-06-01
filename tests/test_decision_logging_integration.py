import json
import sqlite3
from datetime import date

from api.score_pipeline.score_store import store_score
from api.strategy.decision_logger import log_strategy_decision


def test_decision_logging_and_score_store_round_trip():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    assert log_strategy_decision(conn, enabled=False, decision_id="d0", as_of_date=date(2026, 5, 27), decision_type="x", payload={}) is False
    assert log_strategy_decision(conn, enabled=True, decision_id="d1", as_of_date=date(2026, 5, 27), decision_type="x", payload={"a": 1}, reason_codes=["ok"]) is True
    store_score(conn, snapshot_id="s1", entity_type="sector", entity_id="S", score_name="common", score_value=.6, confidence=.7, data_quality=.8, reason_codes=["r"])
    decision = conn.execute("SELECT * FROM strategy_decision_logs WHERE decision_id='d1'").fetchone()
    score = conn.execute("SELECT * FROM score_store WHERE snapshot_id='s1'").fetchone()
    assert json.loads(decision["payload_json"]) == {"a": 1}
    assert json.loads(score["reason_codes_json"]) == ["r"]
