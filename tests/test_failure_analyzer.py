from api.optimization.failure_analyzer import analyze_failures


def test_failure_analyzer_assigns_reason_codes():
    reasons = analyze_failures({"false_alarm_rate": .5, "stress_recall": .2, "return_score": 1.0, "robustness_score": .2})
    assert "HIGH_FALSE_ALARM_RATE" in reasons
    assert "MISSED_STRESS" in reasons
    assert "RETURN_ONLY_OVERFIT" in reasons
