import sqlite3
from datetime import UTC, date, datetime

from api.data_contracts import DataQualityMeta, DataSnapshotRef, ParameterVersionRef, ModelVersionRef, ScoreDataPoint
from api.testbed.schema import ensure_testbed_tables


def test_data_contract_score_point_contains_required_refs():
    now = datetime.now(UTC)
    quality = DataQualityMeta("mock", date(2026, 5, 27), now, 0.8, 0.1, False, 0.9, [])
    point = ScoreDataPoint(
        "sector", "SEMICONDUCTOR", "common", 0.6, 0.7, quality, date(2026, 5, 27),
        ParameterVersionRef("p1", "v1", now),
        ModelVersionRef("m", "v1", now),
        ["ok"],
    )
    assert point.data_quality.quality_score == 0.8
    assert point.parameter_version.parameter_set_id == "p1"


def test_testbed_schema_tables_are_created():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_testbed_tables(conn)
    tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"data_snapshots", "feature_store", "score_store", "strategy_decision_logs", "parameter_sets", "optimization_runs", "optimization_candidates", "decision_evaluations"}.issubset(tables)
