from datetime import date

import pytest

from api.new_pipeline.contracts import ScoreOutput
from api.new_pipeline.engines import (
    AllocationEngine,
    MacroRegimeEngine,
    RebalancingEngine,
    RiskBudgetEngine,
    SectorScoringEngine,
    load_sector_definitions,
)
from api.new_pipeline.parameters import ParameterRegistry


def _score(score_id="score:growth", score=0.7, quality=0.9):
    return ScoreOutput(
        score_id,
        "SPY",
        "asset",
        score,
        0.5,
        score - 0.5,
        0.8,
        quality,
        0.8,
        0.2,
        date(2026, 5, 27),
        "new_pipeline_v1",
        "score_v1",
    )


def test_macro_regime_distribution_is_continuous_and_explanation_only():
    macro = MacroRegimeEngine().evaluate([_score("score:growth_momentum", 0.8), _score("score:volatility_stress", 0.4)], ParameterRegistry.from_yaml(), as_of_date=date(2026, 5, 27))
    assert sum(macro.distribution.values()) == pytest.approx(1.0)
    assert macro.dominant_regime_explanation_only is True
    assert not hasattr(macro, "target_weights")


def test_macro_missing_scores_returns_conservative_fallback():
    macro = MacroRegimeEngine().evaluate([], ParameterRegistry.from_yaml(), as_of_date=date(2026, 5, 27))
    assert macro.confidence == 0.0
    assert any(warning.code == "MISSING_MACRO_SCORES" for warning in macro.warnings)


def test_config_driven_sector_scoring_and_missing_component_fallback():
    definitions = load_sector_definitions()
    assert "semiconductor" in definitions
    macro = MacroRegimeEngine().evaluate([_score("score:growth_momentum", 0.8)], ParameterRegistry.from_yaml(), as_of_date=date(2026, 5, 27))
    sector = SectorScoringEngine(definitions).score(
        sector_id="semiconductor",
        macro=macro,
        components={"momentum": 0.8, "valuation": None, "risk_penalty": 0.2},
        as_of_date=date(2026, 5, 27),
        registry=ParameterRegistry.from_yaml(),
        previous_score=0.55,
    )
    assert 0 <= sector.total_score <= 1
    assert "macro_fit" in sector.component_scores
    assert any(warning.code == "MISSING_SECTOR_COMPONENT" for warning in sector.warnings)
    assert sector.score_change == pytest.approx(sector.score - 0.55)


def test_sector_addition_without_core_rewrite_smoke():
    engine = SectorScoringEngine({"new_sector": load_sector_definitions()["broad_market"]})
    macro = MacroRegimeEngine().evaluate([_score()], ParameterRegistry.from_yaml(), as_of_date=date(2026, 5, 27))
    result = engine.score(
        sector_id="new_sector",
        macro=macro,
        components={"momentum": 0.6, "valuation": 0.5, "risk_penalty": 0.3},
        as_of_date=date(2026, 5, 27),
        registry=ParameterRegistry.from_yaml(),
    )
    assert result.sector_id == "new_sector"


def test_risk_budget_and_hard_constraint_gate():
    risk = RiskBudgetEngine().evaluate(
        account_type="irp",
        current_weights={"SPY": 0.8, "CASH": 0.2},
        risky_assets={"SPY"},
        volatility=0.2,
        drawdown=0.1,
        data_quality=0.9,
        registry=ParameterRegistry.from_yaml(),
        as_of_date=date(2026, 5, 27),
    )
    assert risk.constraint_result.blocked is True
    assert any(reason.code == "RISKY_ASSET_LIMIT_BLOCKED" for reason in risk.reason_codes)
    assert risk.risk_capacity == 0


def test_poor_data_quality_does_not_increase_risk():
    risk = RiskBudgetEngine().evaluate(
        account_type="taxable",
        current_weights={"SPY": 0.1},
        risky_assets={"SPY"},
        volatility=0.1,
        drawdown=0.0,
        data_quality=0.3,
        registry=ParameterRegistry.from_yaml(),
        as_of_date=date(2026, 5, 27),
    )
    assert risk.constraint_result.blocked is True
    assert risk.risk_capacity == 0


def test_allocation_current_target_within_range_and_gradual_change():
    registry = ParameterRegistry.from_yaml()
    macro = MacroRegimeEngine().evaluate([_score("score:growth_momentum", 0.8)], registry, as_of_date=date(2026, 5, 27))
    sector = SectorScoringEngine().score(
        sector_id="broad_market",
        macro=macro,
        components={"momentum": 0.8, "valuation": 0.6, "risk_penalty": 0.1},
        as_of_date=date(2026, 5, 27),
        registry=registry,
    )
    risk = RiskBudgetEngine().evaluate(
        account_type="taxable",
        current_weights={"SPY": 0.1},
        risky_assets={"SPY"},
        volatility=0.1,
        drawdown=0.0,
        data_quality=0.9,
        registry=registry,
        as_of_date=date(2026, 5, 27),
    )
    target = AllocationEngine().allocate(asset_id="SPY", sector_score=sector, macro=macro, risk=risk, previous_target=0.05, registry=registry)
    assert target.min_weight <= target.current_target <= target.max_weight
    assert target.current_target - target.previous_target <= 0.05
    assert not any(reason.code == "DOMINANT_REGIME_FIXED_WEIGHT" for reason in target.reason_codes)


def test_rebalancing_overweight_winner_and_falling_reduction_behavior():
    registry = ParameterRegistry.from_yaml()
    macro = MacroRegimeEngine().evaluate([_score()], registry, as_of_date=date(2026, 5, 27))
    risk = RiskBudgetEngine().evaluate(
        account_type="taxable",
        current_weights={"SMH": 0.1},
        risky_assets={"SMH"},
        volatility=0.1,
        drawdown=0,
        data_quality=0.9,
        registry=registry,
        as_of_date=date(2026, 5, 27),
    )
    improving = SectorScoringEngine().score(
        sector_id="semiconductor",
        macro=macro,
        components={"momentum": 0.9, "valuation": 0.5, "risk_penalty": 0.1},
        as_of_date=date(2026, 5, 27),
        registry=registry,
        previous_score=0.4,
    )
    target = AllocationEngine().allocate(asset_id="SMH", sector_score=improving, macro=macro, risk=risk, previous_target=0.1, registry=registry)
    winner = RebalancingEngine().decide(target=target, current_weight=0.25, sector_score=improving, risk=risk, cash_available_score=0.5, turnover_penalty=0.1, is_satellite=True)
    falling = RebalancingEngine().decide(target=target, current_weight=0.25, sector_score=type(improving)(**{**improving.__dict__, "score_change": -0.2}), risk=risk, cash_available_score=0.5, turnover_penalty=0.1, is_satellite=True)
    assert winner.action == "LIMITED_INCREASE"
    assert falling.action == "REDUCE"
