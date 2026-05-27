from api.backtest_judgment.evaluator import evaluate_judgment


def test_judgment_evaluator_metrics_and_unknown_handling():
    decisions = [{"response_mode": "DEFEND"}, {"response_mode": "OBSERVE"}, {"response_mode": "DEFEND"}, {"response_mode": "EXPAND"}]
    labels = ["CRASH", "STRESS", "BENIGN", "UNKNOWN"]
    metrics = evaluate_judgment(decisions, labels)
    assert metrics["stress_recall"] == 0.5
    assert metrics["missed_stress_count"] == 1
    assert metrics["false_alarm_rate"] > 0
    assert "unknown_labels_excluded" in metrics["warnings"]
