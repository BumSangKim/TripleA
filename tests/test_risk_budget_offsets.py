from api.strategy.adaptive_offsets import RiskOffsets
from api.strategy.risk_budget_engine import RiskBudgetEngine, RiskBudgetPolicy, RiskBucketRule


def _policy():
    return RiskBudgetPolicy({
        "AGGRESSIVE_ALPHA": RiskBucketRule(.6, .4, .8),
        "DEFENSIVE_CORE": RiskBucketRule(.3, .1, .5),
        "LIQUIDITY": RiskBucketRule(.1, .0, .3),
    })


def test_risk_budget_offsets_are_optional_and_conservative():
    weights = {"A": .8, "D": .1, "L": .1}
    buckets = {"A": "AGGRESSIVE_ALPHA", "D": "DEFENSIVE_CORE", "L": "LIQUIDITY"}
    neutral = RiskBudgetEngine().apply(weights, buckets, _policy())
    defensive = RiskBudgetEngine().apply(weights, buckets, _policy(), risk_offsets=RiskOffsets(aggressive_alpha_max_offset=-.2, liquidity_min_offset=.1))
    infeasible = RiskBudgetEngine().apply(weights, buckets, _policy(), risk_offsets=RiskOffsets(liquidity_min_offset=2.0))
    assert neutral.bucket_weights["AGGRESSIVE_ALPHA"] <= .8
    assert defensive.bucket_weights["AGGRESSIVE_ALPHA"] <= neutral.bucket_weights["AGGRESSIVE_ALPHA"]
    assert defensive.bucket_weights["LIQUIDITY"] >= neutral.bucket_weights["LIQUIDITY"]
    assert abs(sum(infeasible.bucket_weights.values()) - 1) < 1e-9
