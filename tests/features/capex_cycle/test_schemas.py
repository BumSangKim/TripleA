from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from api.features.capex_cycle.schemas import (
    BioCapexBottleneckScoreResponse,
    CapexCycleScoreResponse,
    CapexScenarioResponse,
    CapexValuationResponse,
    ReasonItem,
    WarningItem,
)


def _reason() -> ReasonItem:
    return ReasonItem(code="AI_CAPEX_CYCLE_COMPUTED", category="feature", detail="fixture")


def _warning() -> WarningItem:
    return WarningItem(code="LOW_DATA_QUALITY", severity="WARNING", source="feature", message="review required")


def test_capex_cycle_score_response_serializes_readonly_explanations():
    response = CapexCycleScoreResponse(
        feature_id="ai_capex_cycle",
        entity_id="ai_capex_universe",
        score=0.62,
        confidence=0.8,
        data_quality=0.75,
        as_of_date=date(2026, 5, 31),
        parameter_version="ai_capex_params_v0.1",
        model_version="capex_cycle_schema_v1",
        reason_codes=[_reason()],
        warnings=[_warning()],
    )

    payload = response.model_dump(mode="json")

    assert payload["as_of_date"] == "2026-05-31"
    assert payload["reason_codes"][0]["code"] == "AI_CAPEX_CYCLE_COMPUTED"
    assert payload["warnings"][0]["severity"] == "WARNING"


def test_bio_bottleneck_response_keeps_component_scores_readonly():
    response = BioCapexBottleneckScoreResponse(
        asset_id="sample_bio_supplier",
        score=0.58,
        confidence=0.7,
        data_quality=0.8,
        component_scores={"structural_moat": 0.6, "demand_momentum": 0.55},
        core_anchor_allowed=False,
        as_of_date=date(2026, 5, 31),
        parameter_version="bio_capex_params_v0.1",
        model_version="bio_bottleneck_schema_v1",
        reason_codes=[ReasonItem(code="BIO_CAPEX_CORE_ANCHOR_BLOCKED", category="risk")],
        warnings=[],
    )

    assert response.component_scores["structural_moat"] == pytest.approx(0.6)
    assert response.core_anchor_allowed is False


def test_scenario_and_valuation_responses_construct_with_required_metadata():
    scenario = CapexScenarioResponse(
        scenario_id="capex_scenario_distribution",
        score=0.51,
        confidence=0.76,
        data_quality=0.82,
        scenario_distribution={"ai_buildout_continues": 0.42, "credit_stress": 0.08},
        dominant_scenario="ai_buildout_continues",
        as_of_date=date(2026, 5, 31),
        parameter_version="scenario_params_v0.1",
        model_version="scenario_schema_v1",
    )
    valuation = CapexValuationResponse(
        asset_id="sample_ai_infra",
        score=0.54,
        confidence=0.71,
        data_quality=0.69,
        fair_value=125.0,
        current_price=100.0,
        fair_value_ratio=1.25,
        target_per=22.0,
        as_of_date=date(2026, 5, 31),
        parameter_version="valuation_params_v0.1",
        model_version="valuation_schema_v1",
    )

    assert scenario.model_dump(mode="json")["dominant_scenario"] == "ai_buildout_continues"
    assert valuation.model_dump(mode="json")["fair_value_ratio"] == 1.25


def test_required_fields_are_enforced():
    with pytest.raises(ValidationError):
        CapexCycleScoreResponse(
            feature_id="ai_capex_cycle",
            entity_id="ai_capex_universe",
            confidence=0.8,
            data_quality=0.75,
            as_of_date=date(2026, 5, 31),
            parameter_version="ai_capex_params_v0.1",
            model_version="capex_cycle_schema_v1",
        )


def test_order_action_execution_and_target_weight_fields_are_not_allowed():
    blocked_fields = {"order_action", "execution_id", "target_weight", "account_id"}
    schema_classes = (
        CapexCycleScoreResponse,
        BioCapexBottleneckScoreResponse,
        CapexScenarioResponse,
        CapexValuationResponse,
    )

    for schema in schema_classes:
        assert blocked_fields.isdisjoint(schema.model_fields)

    with pytest.raises(ValidationError):
        CapexValuationResponse(
            asset_id="sample_ai_infra",
            score=0.54,
            confidence=0.71,
            data_quality=0.69,
            as_of_date=date(2026, 5, 31),
            parameter_version="valuation_params_v0.1",
            model_version="valuation_schema_v1",
            order_action="BUY",
        )
