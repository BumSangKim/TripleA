from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from api.data.capex_feature_materializer import CapexFeatureMaterializer
from api.data.capex_ingestion_service import CapexIngestionRoute, CapexIngestionService
from api.data.capex_jobs import CapexFetchJobRequest
from api.data.capex_models import RawTimeSeriesPoint
from api.data.capex_repository import SqliteCapexRawDataRepository
from api.data.capex_snapshot_builder import CapexRawSnapshotBuilder
from api.features.capex_cycle.report_service import CapexCycleReportService
from api.features.capex_cycle.schemas import (
    BioCapexBottleneckScoreResponse,
    CapexCycleScoreResponse,
    CapexScenarioResponse,
    CapexValuationResponse,
    ReasonItem,
    WarningItem,
)
from api.features.capex_cycle.source_health import compute_capex_source_health
from api.score_pipeline.parameters import ParameterEntry, ParameterRegistry
from api.score_pipeline.plugins.ai_capex_cycle import AICapexCyclePlugin
from api.score_pipeline.plugins.bio_capex_bottleneck import (
    DEMAND_MOMENTUM_COMPONENTS,
    FINANCIAL_QUALITY_COMPONENTS,
    RISK_PENALTY_COMPONENTS,
    STRUCTURAL_MOAT_COMPONENTS,
    BioCapexBottleneckPlugin,
)
from api.score_pipeline.plugins.capex_common import safe_ratio
from api.score_pipeline.plugins.capex_scenario import CapexScenarioEngine
from api.score_pipeline.plugins.valuation_engine import PERBounds, ValuationEngine


DECISION_DATE = date(2026, 5, 31)
DECISION_TIME = datetime(2026, 5, 31, 23, 59, tzinfo=UTC)
EARLY_AVAILABLE = datetime(2026, 5, 30, tzinfo=UTC)
FUTURE_AVAILABLE = datetime(2026, 6, 2, tzinfo=UTC)


class FakeCapexSourceClient:
    client_name = "capex_fixture"
    source_id = "capex_fixture"

    def list_metrics(self):
        return tuple(_metric_payloads())

    def fetch_time_series(self, *, metric_id, start, end, as_of=None):
        return tuple(_metric_payloads()[metric_id])


class FakeReportFeatureService:
    def __init__(self, ai_score, bio_score, scenario, valuation):
        self.ai_score = ai_score
        self.bio_score = bio_score
        self.scenario = scenario
        self.valuation = valuation

    def get_scores(self, *, as_of_date=None, asset_id=None):
        return [self.ai_score, self.bio_score]

    def get_scenario(self, *, as_of_date=None):
        return self.scenario

    def get_valuation(self, *, asset_id, as_of_date=None):
        return self.valuation


class FakeReportRepository:
    def __init__(self, snapshot_id: str):
        self.snapshot_id = snapshot_id

    def get_universe_metadata(self, *, as_of_date=None):
        return {"data_snapshot_id": self.snapshot_id}


def make_repo() -> SqliteCapexRawDataRepository:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return SqliteCapexRawDataRepository(conn)


def test_capex_etl_to_report_smoke_covers_input_to_output_path() -> None:
    report = _run_pipeline()

    payload = report.model_dump(mode="json")
    assert payload["source_health"]
    assert payload["ai_capex_score"]["reason_codes"]
    assert payload["scenario_distribution"]["scenario_distribution"]
    assert payload["valuation_views"][0]["fair_value"] is not None
    assert payload["versions"]["score_model_versions"]
    assert payload["reason_codes"]
    assert payload["warnings"]

    serialized = json.dumps(payload, sort_keys=True)
    for blocked in ("order_action", "order_id", "execution_id", "target_weight", "broker_order_id"):
        assert blocked not in serialized


def test_capex_etl_to_report_smoke_is_deterministic_for_scores() -> None:
    first = _run_pipeline()
    second = _run_pipeline()

    assert first.ai_capex_score.score == second.ai_capex_score.score
    assert first.scenario_distribution.scenario_distribution == second.scenario_distribution.scenario_distribution
    assert first.valuation_views[0].fair_value == second.valuation_views[0].fair_value
    assert first.versions.parameter_versions == second.versions.parameter_versions


def test_capex_etl_smoke_test_has_no_network_secret_or_execution_imports() -> None:
    source = Path("tests/integration/test_capex_etl_to_report_smoke.py").read_text()
    forbidden = (
        "req" + "uests",
        "htt" + "px",
        "os." + "environ",
        "API" + "_KEY",
        "api." + "brokers",
        "api.features." + "orders",
        "api." + "strategy",
        "submit_" + "order",
        "place_" + "order",
    )

    assert not any(term in source for term in forbidden)


def _run_pipeline():
    repo = make_repo()
    metrics = tuple(_metric_payloads())
    ingestion = CapexIngestionService(
        repository=repo,
        routes={
            "capex_fixture": CapexIngestionRoute(
                source_id="capex_fixture",
                kind="time_series",
                client=FakeCapexSourceClient(),
            )
        },
    )
    dry_run = ingestion.run_fetch_job(_job(metrics, dry_run=True))
    assert dry_run.rows_fetched > 0
    assert dry_run.rows_stored == 0
    assert repo.read_time_series(metric_id="ai.capex.yoy") == ()

    normal = ingestion.run_fetch_job(_job(metrics, dry_run=False))
    repeat = ingestion.run_fetch_job(_job(metrics, dry_run=False))
    assert normal.rows_stored == repeat.rows_stored
    assert len(repo.read_time_series(metric_id="ai.capex.yoy")) == 1

    builder = CapexRawSnapshotBuilder(repository=repo)
    early_snapshot = builder.build(decision_time=DECISION_TIME, metric_ids=metrics)
    later_snapshot = builder.build(decision_time=FUTURE_AVAILABLE + timedelta(days=1), metric_ids=metrics)
    assert early_snapshot.points["ai.token_proxy.index"].value == 1.34
    assert later_snapshot.points["ai.token_proxy.index"].value == 9.99

    materializer = CapexFeatureMaterializer()
    ai_materialized = materializer.materialize_ai(early_snapshot)
    bio_materialized = materializer.materialize_bio(early_snapshot)
    registry = _registry()
    ai_output = AICapexCyclePlugin().compute(ai_materialized.snapshot, registry)
    bio_breakdown = BioCapexBottleneckPlugin().compute_breakdown(bio_materialized.snapshot, registry)
    scenario_result = _scenario(ai_materialized, ai_output.normalized_value)
    valuation_result = ValuationEngine().evaluate(
        asset_id="sample_ai",
        as_of_date=DECISION_DATE,
        forward_eps=2.0,
        midcycle_eps=1.5,
        base_per=20.0,
        last_price=30.0,
        macro_multiplier=1.0,
        per_bounds=PERBounds(min_per=10.0, max_per=30.0),
    )
    report_service = CapexCycleReportService(
        feature_service=FakeReportFeatureService(
            _ai_response(ai_output),
            _bio_response(bio_breakdown),
            _scenario_response(scenario_result),
            _valuation_response(valuation_result),
        ),
        repository=FakeReportRepository(early_snapshot.snapshot_id),
        source_health_provider=lambda as_of_date: compute_capex_source_health(repo, as_of_date=as_of_date),
    )
    return report_service.get_report(as_of_date=DECISION_DATE, asset_ids=("sample_ai",))


def _metric_payloads() -> dict[str, tuple[RawTimeSeriesPoint, ...]]:
    payloads = {
        "ai.capex.yoy": (_point("ai.capex.yoy", "0.18", "year_over_year_change"),),
        "ai.capex.acceleration": (_point("ai.capex.acceleration", "0.04", "quarter_over_quarter_delta"),),
        "ai.token_proxy.index": (
            _point("ai.token_proxy.index", "1.34", "index_level"),
            _point("ai.token_proxy.index", "9.99", "index_level", available_at=FUTURE_AVAILABLE),
        ),
        "token_proxy_index_prev": (_point("token_proxy_index_prev", "1.00", "index_level"),),
    }
    for key in (
        *STRUCTURAL_MOAT_COMPONENTS,
        *DEMAND_MOMENTUM_COMPONENTS,
        *FINANCIAL_QUALITY_COMPONENTS,
        *RISK_PENALTY_COMPONENTS,
    ):
        payloads[key] = (_point(key, "0.50", "ratio"),)
    return payloads


def _point(metric_id: str, value: str, unit: str, *, available_at: datetime = EARLY_AVAILABLE) -> RawTimeSeriesPoint:
    observed = available_at.date()
    return RawTimeSeriesPoint(
        source="capex_fixture",
        source_id="capex_fixture",
        metric_id=metric_id,
        observation_date=observed,
        value=Decimal(value),
        unit=unit,
        available_at=available_at,
        updated_at=available_at,
    )


def _job(metric_ids: tuple[str, ...], *, dry_run: bool) -> CapexFetchJobRequest:
    return CapexFetchJobRequest(
        request_id=f"fixture-{dry_run}",
        source_id="capex_fixture",
        metric_ids=metric_ids,
        start_date=DECISION_DATE - timedelta(days=365),
        end_date=DECISION_DATE,
        requested_at=EARLY_AVAILABLE,
        dry_run=dry_run,
        as_of=DECISION_TIME,
    )


def _scenario(ai_materialized, ai_score: float):
    points = ai_materialized.points
    token_change = points["token_proxy_index"].value - points["token_proxy_index_prev"].value
    return CapexScenarioEngine().evaluate(
        as_of_date=DECISION_DATE,
        ai_capex_cycle_score=ai_score,
        tcr=safe_ratio(token_change, abs(points["token_proxy_index_prev"].value)),
        tce=safe_ratio(token_change, abs(points["bigtech_ai_capex_yoy"].value)),
        capex_acceleration=points["bigtech_ai_capex_accel"].value,
        macro_multiplier=1.0,
        data_quality=1.0,
    )


def _ai_response(output) -> CapexCycleScoreResponse:
    return CapexCycleScoreResponse(
        feature_id=output.feature_id,
        entity_id=output.entity_id,
        score=output.normalized_value,
        confidence=output.confidence,
        data_quality=output.data_quality.quality_score,
        as_of_date=output.as_of_date,
        parameter_version=output.parameter_version,
        model_version=output.model_version,
        reason_codes=[ReasonItem(code=item.code, category=item.category, detail=item.detail) for item in output.reason_codes],
        warnings=[_warning(item.code, item.severity, item.source, item.message) for item in output.warnings],
    )


def _bio_response(breakdown) -> BioCapexBottleneckScoreResponse:
    return BioCapexBottleneckScoreResponse(
        asset_id=breakdown.asset_id,
        score=breakdown.final_score,
        confidence=breakdown.confidence,
        data_quality=breakdown.data_quality,
        component_scores={
            "structural_moat": breakdown.structural_moat,
            "demand_momentum": breakdown.demand_momentum,
            "financial_quality": breakdown.financial_quality,
            "risk_penalty": breakdown.risk_penalty,
        },
        core_anchor_allowed=True,
        as_of_date=breakdown.as_of_date,
        parameter_version=breakdown.parameter_version,
        model_version=breakdown.model_version,
        reason_codes=[ReasonItem(code=item.code, category=item.category, detail=item.detail) for item in breakdown.reason_codes],
        warnings=[_warning(item.code, item.severity, item.source, item.message) for item in breakdown.warnings],
    )


def _scenario_response(result) -> CapexScenarioResponse:
    return CapexScenarioResponse(
        scenario_id="capex_scenario_distribution",
        score=max(result.distribution.values()),
        confidence=result.confidence,
        data_quality=result.data_quality,
        scenario_distribution=result.distribution,
        dominant_scenario=result.dominant_scenario,
        as_of_date=result.as_of_date,
        parameter_version=result.parameter_version,
        model_version=result.model_version,
        reason_codes=[ReasonItem(code=item.code, category=item.category, detail=item.detail) for item in result.reason_codes],
        warnings=[_warning(item.code, item.severity, item.source, item.message) for item in result.warnings],
    )


def _valuation_response(result) -> CapexValuationResponse:
    return CapexValuationResponse(
        asset_id=result.asset_id,
        score=0.5,
        confidence=result.confidence,
        data_quality=result.data_quality,
        fair_value=result.fair_value,
        current_price=result.last_price,
        fair_value_ratio=result.fair_value_ratio,
        target_per=result.target_per,
        as_of_date=result.as_of_date,
        parameter_version=result.parameter_version,
        model_version=result.model_version,
        reason_codes=[ReasonItem(code=item.code, category=item.category, detail=item.detail) for item in result.reason_codes],
        warnings=[_warning(item.code, item.severity, item.source, item.message) for item in result.warnings],
    )


def _warning(code: str, severity: str, source: str, message: str) -> WarningItem:
    return WarningItem(code=code, severity=severity, source=source, message=message)


def _registry() -> ParameterRegistry:
    entries = [
        _entry(
            "ai_cycle_weights",
            {
                "capex_growth": 0.30,
                "demand_momentum": 0.25,
                "supply_constraint": 0.20,
                "profitability_quality": 0.15,
                "data_quality": 0.10,
            },
        ),
        _entry("stale_after_days", 180),
        _entry("quality_min_required", 0.70),
        _entry("final_score_weights", {"structural_moat": 0.40, "demand_momentum": 0.35, "financial_quality": 0.25, "risk_penalty_multiplier": 0.35}),
        _entry("structural_moat_weights", {key: 1.0 / len(STRUCTURAL_MOAT_COMPONENTS) for key in STRUCTURAL_MOAT_COMPONENTS}),
        _entry("demand_momentum_weights", {key: 1.0 / len(DEMAND_MOMENTUM_COMPONENTS) for key in DEMAND_MOMENTUM_COMPONENTS}),
        _entry("financial_quality_weights", {key: 1.0 / len(FINANCIAL_QUALITY_COMPONENTS) for key in FINANCIAL_QUALITY_COMPONENTS}),
        _entry("risk_penalty_weights", {key: 1.0 / len(RISK_PENALTY_COMPONENTS) for key in RISK_PENALTY_COMPONENTS}),
    ]
    return ParameterRegistry(entries)


def _entry(name: str, value) -> ParameterEntry:
    return ParameterEntry(
        name=name,
        value=value,
        version="capex_etl_smoke_v1",
        valid_from=DECISION_DATE - timedelta(days=365),
        valid_to=None,
        source="test",
        reason="capex etl smoke fixture",
        approved=True,
        affected_modules=["score_pipeline"],
    )
