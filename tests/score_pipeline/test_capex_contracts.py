from datetime import date

import pytest

from api.score_pipeline.contracts import (
    BottleneckScoreBreakdown,
    DecisionWarning,
    FeatureOutput,
    PipelineContractError,
    ReasonCode,
    ScenarioDistribution,
    ScoreOutput,
    ValuationResult,
)


def test_scenario_distribution_valid_fields_and_preserves_audit_metadata():
    reason = ReasonCode("CAPEX_SCENARIO_BUILT", "scenario")
    warning = DecisionWarning("LOW_SOURCE_COVERAGE", "WARNING", "capex", "partial fixture coverage")
    result = ScenarioDistribution(
        as_of_date=date(2026, 5, 31),
        distribution={"base": 0.55, "upside": 0.35, "downside": 0.10},
        dominant_scenario="base",
        confidence=0.8,
        data_quality=0.9,
        reason_codes=[reason],
        warnings=[warning],
        parameter_version="capex_params_v1",
        model_version="capex_scenario_v1",
    )

    assert result.distribution["base"] == pytest.approx(0.55)
    assert result.reason_codes == [reason]
    assert result.warnings == [warning]


def test_scenario_distribution_does_not_auto_normalize_probabilities():
    result = ScenarioDistribution(
        as_of_date=date(2026, 5, 31),
        distribution={"base": 0.60, "upside": 0.60},
        dominant_scenario="base",
        confidence=0.7,
        data_quality=0.7,
        reason_codes=[],
        warnings=[],
        parameter_version="capex_params_v1",
        model_version="capex_scenario_v1",
    )

    assert sum(result.distribution.values()) == pytest.approx(1.2)


def test_scenario_distribution_rejects_invalid_ratio_values():
    with pytest.raises(PipelineContractError, match="distribution value"):
        ScenarioDistribution(
            as_of_date=date(2026, 5, 31),
            distribution={"base": 1.2},
            dominant_scenario="base",
            confidence=0.7,
            data_quality=0.7,
            reason_codes=[],
            warnings=[],
            parameter_version="capex_params_v1",
            model_version="capex_scenario_v1",
        )


def test_valuation_result_preserves_nullable_fields():
    warning = DecisionWarning("MISSING_EPS_INPUT", "WARNING", "valuation", "eps was unavailable")
    result = ValuationResult(
        asset_id="BIO_INFRA",
        forward_eps=None,
        midcycle_eps=None,
        eps_persistence=None,
        base_per=None,
        target_per=None,
        macro_multiplier=None,
        fair_value=None,
        last_price=None,
        fair_value_ratio=None,
        confidence=0.0,
        data_quality=0.2,
        as_of_date=date(2026, 5, 31),
        parameter_version="capex_params_v1",
        model_version="capex_valuation_v1",
        reason_codes=[ReasonCode("VALUATION_REVIEW_REQUIRED", "valuation")],
        warnings=[warning],
    )

    assert result.forward_eps is None
    assert result.last_price is None
    assert result.fair_value_ratio is None
    assert result.warnings == [warning]


def test_valuation_result_validates_eps_persistence_when_present():
    with pytest.raises(PipelineContractError, match="eps_persistence"):
        ValuationResult(
            asset_id="BIO_INFRA",
            forward_eps=1.2,
            midcycle_eps=1.0,
            eps_persistence=1.5,
            base_per=20.0,
            target_per=21.0,
            macro_multiplier=1.0,
            fair_value=21.0,
            last_price=18.0,
            fair_value_ratio=1.1667,
            confidence=0.8,
            data_quality=0.8,
            as_of_date=date(2026, 5, 31),
            parameter_version="capex_params_v1",
            model_version="capex_valuation_v1",
        )


def test_bottleneck_score_breakdown_validates_components():
    breakdown = BottleneckScoreBreakdown(
        asset_id="BIO_INFRA",
        structural_moat=0.7,
        demand_momentum=0.6,
        financial_quality=0.8,
        risk_penalty=0.2,
        final_score=0.57,
        confidence=0.75,
        data_quality=0.85,
        as_of_date=date(2026, 5, 31),
        parameter_version="capex_params_v1",
        model_version="capex_score_v1",
        reason_codes=[ReasonCode("BOTTLENECK_SCORE_FLOW", "score")],
    )

    assert breakdown.final_score == pytest.approx(0.57)
    assert breakdown.risk_penalty == pytest.approx(0.2)


def test_existing_public_contract_imports_still_work():
    assert FeatureOutput.__name__ == "FeatureOutput"
    assert ScoreOutput.__name__ == "ScoreOutput"
