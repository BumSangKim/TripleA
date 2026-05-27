from __future__ import annotations


def analyze_failures(metrics: dict) -> list[str]:
    reasons = []
    if metrics.get("false_alarm_rate", 0.0) > 0.4:
        reasons.append("HIGH_FALSE_ALARM_RATE")
    if metrics.get("stress_recall", 1.0) < 0.5:
        reasons.append("MISSED_STRESS")
    if metrics.get("turnover", 0.0) > 1.0:
        reasons.append("TURNOVER_TOO_HIGH")
    if metrics.get("max_drawdown", 0.0) < -0.25:
        reasons.append("MDD_TOO_HIGH")
    if metrics.get("parameter_convergence_score", 1.0) < 0.5:
        reasons.append("LOW_PARAMETER_CONVERGENCE")
    if metrics.get("return_score", 0.0) > 0.9 and metrics.get("robustness_score", 1.0) < 0.5:
        reasons.append("RETURN_ONLY_OVERFIT")
    return reasons
