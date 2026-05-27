from __future__ import annotations

import sqlite3

from api.optimization.candidate_generator import generate_initial_candidates
from api.optimization.objective import candidate_failure_reasons, composite_objective
from api.optimization.parameter_store import create_parameter_set
from api.optimization.run_store import create_optimization_candidate, create_optimization_run, update_optimization_candidate_result, update_optimization_run_status


def run_recursive_optimization_v1(conn: sqlite3.Connection, optimization_run_id: str, *, limit: int = 4) -> dict:
    create_optimization_run(conn, optimization_run_id)
    survivors = []
    for idx, params in enumerate(generate_initial_candidates(limit=limit)):
        parameter_set_id = create_parameter_set(conn, params)
        candidate_id = f"{optimization_run_id}_candidate_{idx}"
        create_optimization_candidate(conn, candidate_id, optimization_run_id, parameter_set_id)
        metrics = {
            "judgment_score": 0.65 + idx * 0.02,
            "survival_score": 0.7,
            "robustness_score": 0.6,
            "cost_discipline_score": 0.8,
            "return_score": 0.5 + idx * 0.05,
        }
        score = composite_objective(metrics)
        failures = candidate_failure_reasons(metrics)
        status = "rejected" if failures else "survivor"
        update_optimization_candidate_result(conn, candidate_id, status, {**metrics, "composite_score": score}, failures)
        if status == "survivor":
            survivors.append(candidate_id)
    update_optimization_run_status(conn, optimization_run_id, "completed", {"survivor_count": len(survivors)})
    return {"optimization_run_id": optimization_run_id, "survivors": survivors}
