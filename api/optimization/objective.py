from __future__ import annotations


def composite_objective(metrics: dict) -> float:
    return max(0.0, min(1.0,
        metrics.get("judgment_score", 0.0) * 0.35
        + metrics.get("survival_score", 0.0) * 0.25
        + metrics.get("robustness_score", 0.0) * 0.20
        + metrics.get("cost_discipline_score", 0.0) * 0.15
        + metrics.get("return_score", 0.0) * 0.05
    ))


def candidate_failure_reasons(metrics: dict, judgment_threshold: float = 0.6) -> list[str]:
    reasons = []
    if metrics.get("judgment_score", 0.0) < judgment_threshold:
        reasons.append("LOW_JUDGMENT_SCORE")
    if metrics.get("return_score", 0.0) > 0.9 and metrics.get("robustness_score", 0.0) < 0.5:
        reasons.append("RETURN_ONLY_OVERFIT")
    return reasons
