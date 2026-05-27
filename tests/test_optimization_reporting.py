from api.optimization.reporting import build_optimization_report


def test_optimization_report_lists_survivors_and_rejected_high_return():
    report = build_optimization_report("run1", [
        {"candidate_id": "c1", "status": "survivor", "parameter_set_id": "p1", "metrics": {"robustness_score": .8}, "failure_reasons": []},
        {"candidate_id": "c2", "status": "rejected", "parameter_set_id": "p2", "metrics": {"return_score": .95}, "failure_reasons": ["RETURN_ONLY_OVERFIT"]},
    ])
    assert report["survivor_count"] == 1
    assert report["rejected_high_return_candidates"][0]["candidate_id"] == "c2"
    assert report["failure_summary"]["RETURN_ONLY_OVERFIT"] == 1
