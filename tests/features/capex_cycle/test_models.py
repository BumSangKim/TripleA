from __future__ import annotations

from dataclasses import fields
from datetime import date

import pytest

from api.features.capex_cycle.models import (
    CapexCycleModelError,
    CapexDecisionAuditRow,
    CapexScenarioSnapshot,
    CapexScoreSnapshot,
    CapexValuationSnapshot,
)
from api.features.capex_cycle.schemas import ReasonItem, WarningItem


AS_OF_DATE = date(2026, 5, 31)


def _reason() -> ReasonItem:
    return ReasonItem(code="AI_CAPEX_CYCLE_COMPUTED", category="feature", detail="fixture")


def _warning() -> WarningItem:
    return WarningItem(code="LOW_DATA_QUALITY", severity="WARNING", source="feature", message="review required")


def test_score_snapshot_construction_and_serialization_preserve_explanations():
    snapshot = CapexScoreSnapshot(
        snapshot_id="score-snap-1",
        score_type="ai_capex_cycle",
        entity_id="ai_infrastructure",
        score=0.62,
        confidence=0.81,
        data_quality=0.74,
        as_of_date=AS_OF_DATE,
        parameter_version="params_v1",
        model_version="model_v1",
        reason_codes=[_reason()],
        warnings=[_warning()],
        payload={"source": "fixture"},
    )

    payload = snapshot.to_dict()

    assert payload["as_of_date"] == "2026-05-31"
    assert payload["reason_codes"][0]["code"] == "AI_CAPEX_CYCLE_COMPUTED"
    assert payload["warnings"][0]["message"] == "review required"
    assert payload["payload"] == {"source": "fixture"}


def test_scenario_and_valuation_snapshots_have_required_version_fields():
    scenario = CapexScenarioSnapshot(
        snapshot_id="scenario-snap-1",
        scenario_id="capex_scenario_distribution",
        scenario_distribution={"ai_buildout_continues": 0.5, "credit_stress": 0.1},
        dominant_scenario="ai_buildout_continues",
        confidence=0.8,
        data_quality=0.75,
        as_of_date=AS_OF_DATE,
        parameter_version="scenario_params_v1",
        model_version="scenario_model_v1",
    )
    valuation = CapexValuationSnapshot(
        snapshot_id="valuation-snap-1",
        asset_id="sample_ai_infra",
        confidence=0.0,
        data_quality=0.0,
        as_of_date=AS_OF_DATE,
        parameter_version="valuation_params_v1",
        model_version="valuation_model_v1",
        fair_value=None,
        fair_value_ratio=None,
    )

    assert scenario.to_dict()["parameter_version"] == "scenario_params_v1"
    assert valuation.to_dict()["fair_value"] is None
    assert valuation.to_dict()["fair_value_ratio"] is None


def test_decision_audit_row_requires_reproducibility_metadata():
    row = CapexDecisionAuditRow(
        audit_id="audit-1",
        snapshot_id="score-snap-1",
        as_of_date=AS_OF_DATE,
        decision_type="read_only_capex_report",
        parameter_version="params_v1",
        model_version="model_v1",
        data_quality=0.74,
        reason_codes=[_reason()],
        warnings=[_warning()],
    )

    assert row.to_dict()["snapshot_id"] == "score-snap-1"
    assert row.to_dict()["reason_codes"][0]["category"] == "feature"


def test_required_fields_are_validated():
    with pytest.raises(CapexCycleModelError, match="snapshot_id"):
        CapexScoreSnapshot(
            snapshot_id="",
            score_type="ai_capex_cycle",
            entity_id="ai_infrastructure",
            score=0.62,
            confidence=0.81,
            data_quality=0.74,
            as_of_date=AS_OF_DATE,
            parameter_version="params_v1",
            model_version="model_v1",
        )
    with pytest.raises(CapexCycleModelError, match="parameter_version"):
        CapexDecisionAuditRow(
            audit_id="audit-1",
            snapshot_id="score-snap-1",
            as_of_date=AS_OF_DATE,
            decision_type="read_only_capex_report",
            parameter_version="",
            model_version="model_v1",
            data_quality=0.74,
        )


def test_models_do_not_include_execution_or_order_fields():
    blocked_fields = {
        "order_id",
        "order_action",
        "execution_id",
        "fill_id",
        "target_weight",
        "account_id",
    }
    model_classes = (CapexScoreSnapshot, CapexScenarioSnapshot, CapexValuationSnapshot, CapexDecisionAuditRow)

    for model in model_classes:
        assert blocked_fields.isdisjoint({field.name for field in fields(model)})
