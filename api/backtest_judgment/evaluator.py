from __future__ import annotations


STRESS_LABELS = {"STRESS", "CRASH"}
DEFENSIVE_MODES = {"DEFEND", "DE_RISK"}


def evaluate_judgment(decisions: list[dict], labels: list[str]) -> dict:
    pairs = [(d, label) for d, label in zip(decisions, labels, strict=False) if label != "UNKNOWN"]
    stress = [pair for pair in pairs if pair[1] in STRESS_LABELS]
    defensive = [pair for pair in pairs if pair[0].get("response_mode") in DEFENSIVE_MODES]
    stress_hits = [pair for pair in stress if pair[0].get("response_mode") in DEFENSIVE_MODES]
    false_alarms = [pair for pair in defensive if pair[1] == "BENIGN"]
    missed = [pair for pair in stress if pair[0].get("response_mode") in {"OBSERVE", "EXPAND"}]
    changes = sum(1 for a, b in zip(decisions, decisions[1:], strict=False) if a.get("response_mode") != b.get("response_mode"))
    total = max(len(pairs), 1)
    stress_recall = len(stress_hits) / max(len(stress), 1)
    stress_precision = len(stress_hits) / max(len(defensive), 1)
    false_alarm_rate = len(false_alarms) / total
    stability = 1.0 - changes / max(len(decisions) - 1, 1)
    judgment_score = max(0.0, min(1.0, stress_recall * 0.35 + stress_precision * 0.25 + stability * 0.25 + (1 - false_alarm_rate) * 0.15))
    return {
        "stress_recall": stress_recall,
        "stress_precision": stress_precision,
        "false_alarm_rate": false_alarm_rate,
        "missed_stress_count": len(missed),
        "recovery_detection_delay": 0,
        "whipsaw_rate": 1 - stability,
        "response_mode_stability": stability,
        "decision_convergence_score": stability,
        "judgment_score": judgment_score,
        "warnings": ["unknown_labels_excluded"] if len(pairs) != len(labels) else [],
    }
