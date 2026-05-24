from api.strategy.risk_budget_engine import (
    RiskBudgetEngine,
    RiskBudgetPolicy,
    RiskBucketRule,
)


def test_risk_budget_engine_clamps_bucket_max_and_minimums():
    result = RiskBudgetEngine().apply(
        asset_weights={
            "SPY": 0.90,
            "TLT": 0.10,
            "CASH_KRW": 0.0,
        },
        asset_to_bucket={
            "SPY": "AGGRESSIVE_ALPHA",
            "TLT": "DEFENSIVE_CORE",
            "CASH_KRW": "LIQUIDITY",
        },
        policy=RiskBudgetPolicy(
            buckets={
                "AGGRESSIVE_ALPHA": RiskBucketRule(target=0.45, min=0.25, max=0.65),
                "DEFENSIVE_CORE": RiskBucketRule(target=0.40, min=0.25, max=0.60),
                "LIQUIDITY": RiskBucketRule(target=0.15, min=0.05, max=0.30),
            }
        ),
    )

    assert result.bucket_weights["AGGRESSIVE_ALPHA"] <= 0.65
    assert result.bucket_weights["DEFENSIVE_CORE"] >= 0.25
    assert result.bucket_weights["LIQUIDITY"] >= 0.05
    assert round(sum(result.adjusted_weights.values()), 6) == 1.0
    assert all(weight >= 0 for weight in result.adjusted_weights.values())
    assert "AGGRESSIVE_ALPHA above max" in result.violations
    assert "LIQUIDITY below min" in result.violations


def test_risk_budget_engine_preserves_bucket_internal_proportions():
    result = RiskBudgetEngine().apply(
        asset_weights={
            "SPY": 0.45,
            "QQQ": 0.45,
            "TLT": 0.10,
        },
        asset_to_bucket={
            "SPY": "AGGRESSIVE_ALPHA",
            "QQQ": "AGGRESSIVE_ALPHA",
            "TLT": "DEFENSIVE_CORE",
        },
        policy=RiskBudgetPolicy(
            buckets={
                "AGGRESSIVE_ALPHA": RiskBucketRule(target=0.50, min=0.20, max=0.70),
                "DEFENSIVE_CORE": RiskBucketRule(target=0.50, min=0.30, max=0.80),
            }
        ),
    )

    assert round(result.adjusted_weights["SPY"], 6) == round(result.adjusted_weights["QQQ"], 6)
    assert round(sum(result.adjusted_weights.values()), 6) == 1.0
