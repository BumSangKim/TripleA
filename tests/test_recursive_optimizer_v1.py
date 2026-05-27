import sqlite3

from api.optimization.optimizer import run_recursive_optimization_v1
from api.optimization.run_store import list_candidates_for_run


def test_recursive_optimizer_stores_candidates_without_promotion():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    result = run_recursive_optimization_v1(conn, "run1", limit=2)
    candidates = list_candidates_for_run(conn, "run1")
    assert len(candidates) == 2
    assert result["survivors"]
    assert all(candidate["status"] in {"survivor", "rejected"} for candidate in candidates)
