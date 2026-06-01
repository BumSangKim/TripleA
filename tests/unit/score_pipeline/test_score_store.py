import json
import sqlite3

from api.score_pipeline.score_store import store_score


def test_store_score_inserts_score_store_row():
    conn = _conn()

    store_score(
        conn,
        snapshot_id="s1",
        entity_type="sector",
        entity_id="SEMICONDUCTOR",
        score_name="common",
        score_value=0.6,
        confidence=0.7,
        data_quality=0.8,
        reason_codes=["momentum", "relative_strength"],
    )

    row = conn.execute("SELECT * FROM score_store WHERE snapshot_id='s1'").fetchone()

    assert row["entity_type"] == "sector"
    assert row["entity_id"] == "SEMICONDUCTOR"
    assert row["score_name"] == "common"
    assert row["score_value"] == 0.6
    assert row["confidence"] == 0.7
    assert row["data_quality"] == 0.8
    assert json.loads(row["reason_codes_json"]) == ["momentum", "relative_strength"]


def test_store_score_updates_same_unique_score_key():
    conn = _conn()

    store_score(
        conn,
        snapshot_id="s1",
        entity_type="sector",
        entity_id="SEMICONDUCTOR",
        score_name="common",
        score_value=0.6,
        confidence=0.7,
        data_quality=0.8,
        reason_codes=["old"],
    )
    store_score(
        conn,
        snapshot_id="s1",
        entity_type="sector",
        entity_id="SEMICONDUCTOR",
        score_name="common",
        score_value=0.9,
        confidence=0.4,
        data_quality=0.5,
        reason_codes=["new"],
    )

    rows = conn.execute("SELECT * FROM score_store").fetchall()

    assert len(rows) == 1
    assert rows[0]["score_value"] == 0.9
    assert rows[0]["confidence"] == 0.4
    assert rows[0]["data_quality"] == 0.5
    assert json.loads(rows[0]["reason_codes_json"]) == ["new"]


def test_store_score_persists_reason_codes_as_deterministic_json():
    conn = _conn()

    store_score(
        conn,
        snapshot_id="s1",
        entity_type="sector",
        entity_id="S",
        score_name="common",
        score_value=0.6,
        confidence=0.7,
        data_quality=0.8,
        reason_codes=["b", "a"],
    )

    row = conn.execute("SELECT reason_codes_json FROM score_store").fetchone()

    assert row["reason_codes_json"] == '["b", "a"]'


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn
