import sqlite3

from api.optimization.parameter_store import create_parameter_set, get_parameter_set
from api.optimization.run_store import create_optimization_candidate, create_optimization_run, list_candidates_for_run, update_optimization_candidate_result, update_optimization_run_status


def test_parameter_and_optimization_stores_round_trip():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    param_id = create_parameter_set(conn, {"a": 1})
    create_optimization_run(conn, "run1")
    update_optimization_run_status(conn, "run1", "running")
    create_optimization_candidate(conn, "c1", "run1", param_id)
    update_optimization_candidate_result(conn, "c1", "failed", {"return_score": .9}, ["RETURN_ONLY_OVERFIT"])
    assert get_parameter_set(conn, param_id)["parameters"] == {"a": 1}
    assert list_candidates_for_run(conn, "run1")[0]["failure_reasons"] == ["RETURN_ONLY_OVERFIT"]
