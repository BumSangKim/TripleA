from __future__ import annotations

from collections import Counter


def build_optimization_report(optimization_run_id: str, candidates: list[dict]) -> dict:
    survivors = [item for item in candidates if item.get("status") == "survivor"]
    failures = Counter(reason for item in candidates for reason in item.get("failure_reasons", []))
    rejected_high_return = [
        item for item in candidates
        if item.get("metrics", {}).get("return_score", 0.0) > 0.8 and item.get("status") != "survivor"
    ]
    return {
        "optimization_run_id": optimization_run_id,
        "search_method": "coarse_to_fine",
        "initial_candidate_count": len(candidates),
        "survivor_count": len(survivors),
        "parameter_convergence_score": 0.7 if survivors else 0.0,
        "decision_convergence_score": 0.7 if survivors else 0.0,
        "robustness_score": sum(item.get("metrics", {}).get("robustness_score", 0.0) for item in survivors) / max(len(survivors), 1),
        "selected_region": {"candidate_ids": [item["candidate_id"] for item in survivors]},
        "recommended_parameter_set": survivors[0].get("parameter_set_id") if survivors else None,
        "rejected_high_return_candidates": rejected_high_return,
        "failure_summary": dict(failures),
        "warnings": ["no_auto_promotion"],
    }
