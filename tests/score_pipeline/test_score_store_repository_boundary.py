from __future__ import annotations

import sqlite3
from datetime import date

from api.score_pipeline.score_store import SQLiteScoreStore
from api.strategy.score_layer import ScoreOutput


def _output(as_of_date: date, decision_score: float) -> ScoreOutput:
    return ScoreOutput(
        score_key="momentum_score",
        score_type="atomic",
        subject_type="asset",
        subject_id="SMH",
        raw_value=decision_score,
        normalized_score=decision_score,
        smoothed_score=decision_score,
        confidence_adjusted_score=decision_score,
        decision_score=decision_score,
        previous_score=None,
        score_change=0.0,
        confidence=1.0,
        data_quality=1.0,
        stability=1.0,
        smoothing_method="ema",
        base_span=5,
        effective_span=5,
        span_override_applied=False,
        span_override_reason=None,
        event_profile="normal",
        override_expires_at=None,
        reason_codes=["OK"],
        warnings=[],
        as_of_date=as_of_date,
        source_plugin_id="mock_plugin",
        source_feature_key="momentum_3m",
        feature_snapshot_id="snap-1",
        parameter_version="p",
        model_version="m",
    )


def test_score_pipeline_sqlite_store_persists_run_values_and_previous_lookup():
    conn = sqlite3.connect(":memory:")
    store = SQLiteScoreStore(conn)
    output = _output(date(2026, 5, 26), 0.6)

    store.create_run("run-1", "snap-1", output.as_of_date, "normal", "p", "m", "SUCCESS", [])
    store.insert_value("run-1", output)

    rows = store.values_for_run("run-1")
    assert rows[0]["score_key"] == "momentum_score"
    assert rows[0]["decision_score"] == 0.6
    assert store.lookup_previous_score("momentum_score", "asset", "SMH", date(2026, 5, 27)) == 0.6


def test_score_pipeline_sqlite_store_keeps_warning_json_reproducible():
    conn = sqlite3.connect(":memory:")
    store = SQLiteScoreStore(conn)

    store.create_run("run-1", "snap-1", date(2026, 5, 26), "normal", "p", "m", "WARNING", ["b", "a"])

    row = conn.execute("SELECT warnings_json FROM score_runs WHERE run_id='run-1'").fetchone()
    assert row["warnings_json"] == '["b", "a"]'

