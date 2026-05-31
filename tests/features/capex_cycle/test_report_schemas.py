from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from api.features.capex_cycle.report_schemas import (
    CapexAnchorClassification,
    CapexAnchorClassificationItem,
    CapexCycleReportResponse,
    CapexReportVersions,
    SourceHealthItem,
)
from api.features.capex_cycle.schemas import (
    BioCapexBottleneckScoreResponse,
    CapexCycleScoreResponse,
    CapexScenarioResponse,
    CapexValuationResponse,
    ReasonItem,
    WarningItem,
)


AS_OF = date(2026, 5, 31)


def reason() -> ReasonItem:
    return ReasonItem(code="CAPEX_REPORT_ASSEMBLED", category="report", detail="fixture")


def warning() -> WarningItem:
    return WarningItem(code="REVIEW_REQUIRED", severity="WARNING", source="report", message="fixture warning")


def score() -> CapexCycleScoreResponse:
    return CapexCycleScoreResponse(
        feature_id="feature:ai_capex_cycle",
        entity_id="ai_infrastructure",
        score=0.62,
        confidence=0.8,
        data_quality=0.75,
        as_of_date=AS_OF,
        parameter_version="ai_params_v0",
        model_version="ai_model_v0",
        reason_codes=[reason()],
        warnings=[warning()],
    )


def bio() -> BioCapexBottleneckScoreResponse:
    return BioCapexBottleneckScoreResponse(
        asset_id="sample_bio_supplier",
        score=0.58,
        confidence=0.7,
        data_quality=0.8,
        component_scores={"structural_moat": 0.6},
        core_anchor_allowed=False,
        as_of_date=AS_OF,
        parameter_version="bio_params_v0",
        model_version="bio_model_v0",
        reason_codes=[reason()],
        warnings=[warning()],
    )


def scenario() -> CapexScenarioResponse:
    return CapexScenarioResponse(
        scenario_id="capex_scenario_distribution",
        score=0.51,
        confidence=0.76,
        data_quality=0.82,
        scenario_distribution={"ai_buildout_continues": 0.42, "credit_stress": 0.08},
        dominant_scenario="ai_buildout_continues",
        as_of_date=AS_OF,
        parameter_version="scenario_params_v0",
        model_version="scenario_model_v0",
        reason_codes=[reason()],
        warnings=[warning()],
    )


def valuation() -> CapexValuationResponse:
    return CapexValuationResponse(
        asset_id="sample_ai_infra",
        score=0.54,
        confidence=0.71,
        data_quality=0.69,
        fair_value=125.0,
        current_price=100.0,
        fair_value_ratio=1.25,
        target_per=22.0,
        as_of_date=AS_OF,
        parameter_version="valuation_params_v0",
        model_version="valuation_model_v0",
        reason_codes=[reason()],
        warnings=[warning()],
    )


def source_health() -> SourceHealthItem:
    return SourceHealthItem(
        source_id="ECOS",
        status="AVAILABLE",
        quality_score=0.9,
        last_available_at=datetime(2026, 5, 30, tzinfo=timezone.utc),
        warnings=[warning()],
        reason_codes=[reason()],
    )


def versions() -> CapexReportVersions:
    return CapexReportVersions(
        report_schema_version="capex_report_v1",
        data_snapshot_version="snapshot_v1",
        score_model_versions={"ai": "ai_model_v0", "bio": "bio_model_v0"},
        parameter_versions={"ai": "ai_params_v0"},
    )


def report() -> CapexCycleReportResponse:
    return CapexCycleReportResponse(
        as_of_date=AS_OF,
        data_snapshot_id="capex_raw_snapshot_20260531_fixture",
        source_health=[source_health()],
        ai_capex_score=score(),
        bio_bottleneck_scores=[bio()],
        scenario_distribution=scenario(),
        valuation_views=[valuation()],
        anchor_classifications=[
            CapexAnchorClassificationItem(
                asset_id="sample_bio_supplier",
                classification=CapexAnchorClassification.OBSERVATION_ONLY,
                confidence=0.7,
                reason_codes=[reason()],
                warnings=[warning()],
            )
        ],
        warnings=[warning()],
        reason_codes=[reason()],
        versions=versions(),
    )


def test_report_schema_serializes_readonly_sections() -> None:
    payload = report().model_dump(mode="json")

    assert payload["as_of_date"] == "2026-05-31"
    assert payload["data_snapshot_id"].startswith("capex_raw_snapshot")
    assert payload["source_health"][0]["source_id"] == "ECOS"
    assert payload["ai_capex_score"]["score"] == 0.62
    assert payload["scenario_distribution"]["dominant_scenario"] == "ai_buildout_continues"
    assert payload["versions"]["report_schema_version"] == "capex_report_v1"


@pytest.mark.parametrize("missing_field", ["warnings", "reason_codes", "versions"])
def test_warnings_reasons_and_versions_are_required(missing_field: str) -> None:
    data = report().model_dump()
    data.pop(missing_field)

    with pytest.raises(ValidationError):
        CapexCycleReportResponse(**data)


def test_no_execution_or_order_fields_exist() -> None:
    blocked_fields = {
        "order_action",
        "execution_id",
        "target_weight",
        "account_id",
        "broker_order_id",
        "order_id",
    }
    schema_classes = (
        CapexCycleReportResponse,
        CapexAnchorClassificationItem,
        SourceHealthItem,
        CapexReportVersions,
    )

    for schema in schema_classes:
        assert blocked_fields.isdisjoint(schema.model_fields)

    with pytest.raises(ValidationError):
        CapexCycleReportResponse(**{**report().model_dump(), "order_id": "forbidden"})


def test_classification_labels_are_research_only() -> None:
    labels = {item.value for item in CapexAnchorClassification}

    assert "OBSERVATION_ONLY" in labels
    assert "REVIEW_REQUIRED" in labels
    assert all("BUY" not in label and "SELL" not in label and "REDUCE" not in label for label in labels)
