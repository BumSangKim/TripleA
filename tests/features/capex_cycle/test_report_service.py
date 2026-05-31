from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from api.features.capex_cycle.report_schemas import SourceHealthItem
from api.features.capex_cycle.report_service import CapexCycleReportService
from api.features.capex_cycle.schemas import (
    BioCapexBottleneckScoreResponse,
    CapexCycleScoreResponse,
    CapexScenarioResponse,
    CapexValuationResponse,
    ReasonItem,
    WarningItem,
)


AS_OF = date(2026, 5, 31)


def reason(code: str = "FIXTURE_REASON") -> ReasonItem:
    return ReasonItem(code=code, category="fixture")


def warning(code: str = "FIXTURE_WARNING") -> WarningItem:
    return WarningItem(code=code, severity="WARNING", source="fixture", message="fixture warning")


class FakeFeatureService:
    def __init__(self, *, fail_valuation: bool = False):
        self.fail_valuation = fail_valuation

    def get_scores(self, *, as_of_date=None, asset_id=None):
        return [
            CapexCycleScoreResponse(
                feature_id="feature:ai_capex_cycle",
                entity_id="ai_infrastructure",
                score=0.62,
                confidence=0.8,
                data_quality=0.75,
                as_of_date=as_of_date,
                parameter_version="ai_params_v1",
                model_version="ai_model_v1",
                reason_codes=[reason("AI_CAPEX_CYCLE_COMPUTED")],
                warnings=[],
            ),
            BioCapexBottleneckScoreResponse(
                asset_id="sample_bio_supplier",
                score=0.58,
                confidence=0.7,
                data_quality=0.8,
                component_scores={"structural_moat": 0.6},
                core_anchor_allowed=False,
                as_of_date=as_of_date,
                parameter_version="bio_params_v1",
                model_version="bio_model_v1",
                reason_codes=[reason("BIO_CAPEX_BOTTLENECK_COMPUTED")],
                warnings=[warning("BIO_REVIEW")],
            ),
        ]

    def get_scenario(self, *, as_of_date=None):
        return CapexScenarioResponse(
            scenario_id="capex_scenario_distribution",
            score=0.51,
            confidence=0.76,
            data_quality=0.82,
            scenario_distribution={"ai_buildout_continues": 0.42, "credit_stress": 0.08},
            dominant_scenario="ai_buildout_continues",
            as_of_date=as_of_date,
            parameter_version="scenario_params_v1",
            model_version="scenario_model_v1",
            reason_codes=[reason("CAPEX_SCENARIO_COMPUTED")],
            warnings=[],
        )

    def get_valuation(self, *, asset_id, as_of_date=None):
        if self.fail_valuation:
            raise RuntimeError("valuation fixture unavailable")
        return CapexValuationResponse(
            asset_id=asset_id,
            score=0.54,
            confidence=0.71,
            data_quality=0.69,
            fair_value=125.0,
            current_price=100.0,
            fair_value_ratio=1.25,
            target_per=22.0,
            as_of_date=as_of_date,
            parameter_version="valuation_params_v1",
            model_version="valuation_model_v1",
            reason_codes=[reason("CAPEX_VALUATION_COMPUTED")],
            warnings=[],
        )


class FakeRepository:
    def get_universe_metadata(self, *, as_of_date=None):
        return {"data_snapshot_id": f"snapshot-{as_of_date.isoformat()}"}


def source_health_provider(as_of_date: date):
    return [
        SourceHealthItem(
            source_id="ECOS",
            status="AVAILABLE",
            quality_score=0.9,
            last_available_at=datetime(2026, 5, 30, tzinfo=timezone.utc),
            warnings=[],
            reason_codes=[reason("SOURCE_AVAILABLE")],
        )
    ]


def test_normal_report_from_fake_services() -> None:
    service = CapexCycleReportService(
        feature_service=FakeFeatureService(),
        repository=FakeRepository(),
        source_health_provider=source_health_provider,
    )

    report = service.get_report(as_of_date=AS_OF, asset_ids=("sample_ai",))

    assert report.data_snapshot_id == "snapshot-2026-05-31"
    assert report.ai_capex_score.score == 0.62
    assert report.bio_bottleneck_scores[0].asset_id == "sample_bio_supplier"
    assert report.scenario_distribution.dominant_scenario == "ai_buildout_continues"
    assert report.valuation_views[0].fair_value_ratio == 1.25
    assert report.anchor_classifications[0].classification == "OBSERVATION_ONLY"


def test_partial_unavailable_valuation_is_included_with_warning() -> None:
    service = CapexCycleReportService(
        feature_service=FakeFeatureService(fail_valuation=True),
        repository=FakeRepository(),
        source_health_provider=source_health_provider,
    )

    report = service.get_report(as_of_date=AS_OF, asset_ids=("sample_ai",))

    valuation = report.valuation_views[0]
    assert valuation.asset_id == "sample_ai"
    assert valuation.fair_value is None
    assert valuation.confidence == 0.0
    assert any(w.code == "CAPEX_REPORT_SECTION_UNAVAILABLE" for w in report.warnings)
    assert report.versions.score_model_versions["valuation:sample_ai"] == "unavailable"


def test_versions_and_audit_metadata_propagate() -> None:
    service = CapexCycleReportService(
        feature_service=FakeFeatureService(),
        repository=FakeRepository(),
        source_health_provider=source_health_provider,
    )

    report = service.get_report(as_of_date=AS_OF, asset_ids=("sample_ai",))

    assert report.versions.parameter_versions["ai_capex_score"] == "ai_params_v1"
    assert report.versions.score_model_versions["scenario_distribution"] == "scenario_model_v1"
    assert any(r.code == "AI_CAPEX_CYCLE_COMPUTED" for r in report.reason_codes)
    assert any(w.code == "BIO_REVIEW" for w in report.warnings)
    assert report.source_health[0].reason_codes[0].code == "SOURCE_AVAILABLE"


def test_missing_source_health_provider_is_conservative_empty() -> None:
    report = CapexCycleReportService(feature_service=FakeFeatureService(), repository=FakeRepository()).get_report(
        as_of_date=AS_OF,
        asset_ids=("sample_ai",),
    )

    assert report.source_health == []
    assert any(w.code == "SOURCE_HEALTH_UNAVAILABLE" for w in report.warnings)


def test_report_service_has_no_forbidden_imports() -> None:
    source = Path("api/features/capex_cycle/report_service.py").read_text()
    forbidden = (
        "api.brokers",
        "api.features.orders",
        "api.strategy",
        "submit_order",
        "place_order",
        "execute_draft",
    )

    assert not any(term in source for term in forbidden)
