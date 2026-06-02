from __future__ import annotations

from dataclasses import asdict
from datetime import date

from api.domain.scoring.ai_capex_token_contracts import AICapexTokenScenarioDistribution
from api.score_pipeline.plugins.ai_capex_token_sector_diagnostics import (
    SECTOR_IDS,
    build_adaptive_sector_diagnostics,
)


CONFIG = {
    "max_component_contribution": 0.05,
    "valuation_burden_penalty": 0.4,
    "macro_stress_attenuation": 0.5,
    "turnover_penalty": 0.2,
}


def test_component_scores_are_bounded_and_contribution_caps_apply():
    diagnostics = build_adaptive_sector_diagnostics(
        _distribution("S1", probability=0.8),
        _sector_metrics(),
        config=CONFIG,
        macro_stress=0.1,
        stability=0.9,
        turnover_pressure=0.2,
    )

    assert {item.sector_id for item in diagnostics} == set(SECTOR_IDS)
    for item in diagnostics:
        assert 0.0 <= item.component_score <= 1.0
        assert 0.0 <= item.component_contribution <= CONFIG["max_component_contribution"]
        assert item.diagnostic_only is True
        assert item.reason_codes


def test_missing_data_cannot_increase_contribution():
    distribution = _distribution("S1", probability=0.8)
    full = _by_sector(
        build_adaptive_sector_diagnostics(
            distribution,
            _sector_metrics(),
            config=CONFIG,
            macro_stress=0.1,
            stability=0.9,
            turnover_pressure=0.2,
        )
    )
    missing = _by_sector(
        build_adaptive_sector_diagnostics(
            distribution,
            {"power_equipment": {}},
            config=CONFIG,
            macro_stress=0.1,
            stability=0.9,
            turnover_pressure=0.2,
        )
    )

    assert missing["power_equipment"].component_contribution <= full["power_equipment"].component_contribution
    assert missing["power_equipment"].user_review_required is True
    assert any(reason.startswith("missing_") for reason in missing["power_equipment"].reason_codes)


def test_valuation_burden_dampens_continuously_without_hard_switch():
    distribution = _distribution("S1", probability=0.8)
    low_valuation = _sector_metrics()
    high_valuation = _sector_metrics()
    high_valuation["power_equipment"] = {**high_valuation["power_equipment"], "valuation_burden_score": 0.9}

    low = _by_sector(
        build_adaptive_sector_diagnostics(
            distribution,
            low_valuation,
            config=CONFIG,
            macro_stress=0.1,
            stability=0.9,
            turnover_pressure=0.2,
        )
    )
    high = _by_sector(
        build_adaptive_sector_diagnostics(
            distribution,
            high_valuation,
            config=CONFIG,
            macro_stress=0.1,
            stability=0.9,
            turnover_pressure=0.2,
        )
    )

    assert 0.0 < high["power_equipment"].valuation_dampener < low["power_equipment"].valuation_dampener
    assert high["power_equipment"].component_contribution < low["power_equipment"].component_contribution


def test_macro_stress_dampens_risk_contribution_without_redefining_scenario():
    distribution = _distribution("S1", probability=0.8)
    calm = _by_sector(
        build_adaptive_sector_diagnostics(
            distribution,
            _sector_metrics(),
            config=CONFIG,
            macro_stress=0.0,
            stability=0.9,
            turnover_pressure=0.2,
        )
    )
    stressed = _by_sector(
        build_adaptive_sector_diagnostics(
            distribution,
            _sector_metrics(),
            config=CONFIG,
            macro_stress=0.8,
            stability=0.9,
            turnover_pressure=0.2,
        )
    )

    assert stressed["power_equipment"].component_contribution < calm["power_equipment"].component_contribution
    assert distribution.dominant_scenario == "S1"


def test_inverse_hedge_diagnostic_cannot_become_order_candidate():
    diagnostics = _by_sector(
        build_adaptive_sector_diagnostics(
            _distribution("S7", probability=0.8),
            _sector_metrics(),
            config=CONFIG,
            macro_stress=0.5,
            stability=0.9,
            turnover_pressure=0.2,
        )
    )
    inverse = diagnostics["inverse_hedge_diagnostic"]
    payload = asdict(inverse)

    assert inverse.user_review_required is True
    assert inverse.diagnostic_only is True
    assert "inverse_hedge_diagnostic_only" in inverse.reason_codes
    assert {"order", "target_weight", "execution", "allocation"}.isdisjoint(payload)


def _distribution(dominant: str, *, probability: float) -> AICapexTokenScenarioDistribution:
    remaining = (1.0 - probability) / 8.0
    probabilities = {f"S{i}": remaining for i in range(1, 10)}
    probabilities[dominant] = probability
    return AICapexTokenScenarioDistribution(
        as_of_date=date(2026, 1, 31),
        probabilities=probabilities,
        dominant_scenario=dominant,
        dominant_scenario_explanation_only=True,
        data_quality=0.9,
        confidence=0.8,
        parameter_version="adaptive-params-v1",
        model_version="adaptive-model-v1",
    )


def _sector_metrics():
    return {
        "bigtech_platform": {
            "ai_monetization_score": 0.7,
            "fcf_margin_improvement_score": 0.6,
            "capex_burden_score": 0.3,
            "valuation_burden_score": 0.3,
        },
        "power_equipment": {
            "backlog_growth_score": 0.75,
            "asp_growth_score": 0.65,
            "valuation_burden_score": 0.3,
        },
        "semiconductor_hbm": {
            "hbm_asp_growth_score": 0.7,
            "hbm_supply_growth_score": 0.5,
            "hbm_inventory_risk_score": 0.2,
            "valuation_burden_score": 0.4,
        },
    }


def _by_sector(diagnostics):
    return {item.sector_id: item for item in diagnostics}
