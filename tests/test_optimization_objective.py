from api.optimization.objective import candidate_failure_reasons, composite_objective


def test_objective_prioritizes_judgment_not_return_only():
    good_judgment = composite_objective({"judgment_score": .9, "survival_score": .7, "robustness_score": .7, "cost_discipline_score": .7, "return_score": .1})
    return_only = composite_objective({"judgment_score": .2, "survival_score": .7, "robustness_score": .2, "cost_discipline_score": .7, "return_score": 1.0})
    assert good_judgment > return_only
    assert "RETURN_ONLY_OVERFIT" in candidate_failure_reasons({"judgment_score": .7, "return_score": 1.0, "robustness_score": .2})
