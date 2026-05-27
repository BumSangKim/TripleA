from datetime import date

from api.strategy.score_contract import ScoreComponent, clamp_score, combine_reason_codes, confidence_adjusted_score, safe_weighted_average


def test_score_contract_helpers_are_bounded_and_conservative():
    assert clamp_score(1.5) == 1.0
    assert clamp_score(-1) == 0.0
    assert safe_weighted_average([]) == 0.5
    components = [ScoreComponent("a", 1.0, 1.0, 0, ["A"]), ScoreComponent("b", 0.0, 1.0, 0, ["B"])]
    assert safe_weighted_average(components) == 0.5
    assert confidence_adjusted_score(1.0, 0.2, 0.5) == 0.55
    assert combine_reason_codes(["A"], ["A", "B"], "C") == ["A", "B", "C"]
