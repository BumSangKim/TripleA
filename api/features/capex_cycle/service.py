from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from typing import Mapping

from api.data.adapters.fixtures import FixtureCapexInputAdapter, FixtureCompanyMetricAdapter
from api.data.adapters.ports import CapexInputAdapter, CompanyMetricAdapter, TimeSeriesPoint
from api.features.capex_cycle.schemas import (
    BioCapexBottleneckScoreResponse,
    CapexCycleScoreResponse,
    CapexScenarioResponse,
    CapexValuationResponse,
    ReasonItem,
    WarningItem,
)
from api.score_pipeline.contracts import DecisionWarning, ReasonCode
from api.score_pipeline.data_quality import HistoricalSnapshot, RawDataPoint
from api.score_pipeline.parameters import ParameterRegistry
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


@dataclass
class CapexCycleService:
    registry: ParameterRegistry = field(default_factory=ParameterRegistry.from_yaml)
    capex_adapter: CapexInputAdapter = field(default_factory=FixtureCapexInputAdapter)
    company_metric_adapter: CompanyMetricAdapter = field(default_factory=FixtureCompanyMetricAdapter)
    ai_plugin: AICapexCyclePlugin = field(default_factory=AICapexCyclePlugin)
    bio_plugin: BioCapexBottleneckPlugin = field(default_factory=BioCapexBottleneckPlugin)
    scenario_engine: CapexScenarioEngine = field(default_factory=CapexScenarioEngine)
    valuation_engine: ValuationEngine = field(default_factory=ValuationEngine)
    valuation_inputs: Mapping[str, Mapping[str, float | None]] = field(default_factory=dict)
    per_bounds: PERBounds | None = None
    macro_multiplier: float | None = None

    def get_scores(self, *, as_of_date: date | None = None, asset_id: str | None = None):
        decision_date = as_of_date or date.today()
        ai_output = self.ai_plugin.compute(_ai_snapshot(self.capex_adapter, decision_date), self.registry)
        bio_breakdown = self.bio_plugin.compute_breakdown(
            _bio_snapshot(self.capex_adapter, self.company_metric_adapter, decision_date),
            self.registry,
            asset_id=asset_id or "bio_capex_bottleneck",
        )
        return [
            _capex_cycle_response(ai_output),
            _bio_bottleneck_response(bio_breakdown),
        ]

    def get_scenario(self, *, as_of_date: date | None = None) -> CapexScenarioResponse:
        decision_date = as_of_date or date.today()
        ai_snapshot = _ai_snapshot(self.capex_adapter, decision_date)
        ai_output = self.ai_plugin.compute(ai_snapshot, self.registry)
        inputs = _derive_ai_inputs(ai_snapshot)
        scenario = self.scenario_engine.evaluate(
            as_of_date=decision_date,
            ai_capex_cycle_score=ai_output.normalized_value,
            tcr=inputs.get("tcr"),
            tce=inputs.get("tce"),
            capex_acceleration=inputs.get("capex_acceleration"),
            macro_multiplier=self.macro_multiplier,
            data_quality=ai_output.data_quality.quality_score,
        )
        return CapexScenarioResponse(
            scenario_id="capex_scenario_distribution",
            score=max(scenario.distribution.values()) if scenario.distribution else 0.0,
            confidence=scenario.confidence,
            data_quality=scenario.data_quality,
            scenario_distribution=scenario.distribution,
            dominant_scenario=scenario.dominant_scenario,
            as_of_date=scenario.as_of_date,
            parameter_version=scenario.parameter_version,
            model_version=scenario.model_version,
            reason_codes=_reason_items(scenario.reason_codes),
            warnings=_warning_items(scenario.warnings),
        )

    def get_valuation(self, *, asset_id: str, as_of_date: date | None = None) -> CapexValuationResponse:
        decision_date = as_of_date or date.today()
        inputs = self.valuation_inputs.get(asset_id, {})
        if self.per_bounds is None:
            return CapexValuationResponse(
                asset_id=asset_id,
                score=0.5,
                confidence=0.0,
                data_quality=0.0,
                fair_value=None,
                current_price=inputs.get("last_price"),
                fair_value_ratio=None,
                target_per=None,
                as_of_date=decision_date,
                parameter_version="unavailable",
                model_version=self.valuation_engine.model_version,
                reason_codes=[ReasonItem(code="VALUATION_UNAVAILABLE", category="valuation", detail="missing PER bounds")],
                warnings=[
                    WarningItem(
                        code="VALUATION_UNAVAILABLE",
                        severity="WARNING",
                        source="valuation",
                        message="missing valuation inputs",
                    )
                ],
            )
        result = self.valuation_engine.evaluate(
            asset_id=asset_id,
            as_of_date=decision_date,
            forward_eps=inputs.get("forward_eps"),
            midcycle_eps=inputs.get("midcycle_eps"),
            base_per=inputs.get("base_per"),
            last_price=inputs.get("last_price"),
            macro_multiplier=inputs.get("macro_multiplier"),
            per_bounds=self.per_bounds,
            confidence=float(inputs.get("confidence") or 1.0),
            data_quality=float(inputs.get("data_quality") or 1.0),
        )
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
            reason_codes=_reason_items(result.reason_codes),
            warnings=_warning_items(result.warnings),
        )


def _capex_cycle_response(output) -> CapexCycleScoreResponse:
    return CapexCycleScoreResponse(
        feature_id=output.feature_id,
        entity_id=output.entity_id,
        score=output.normalized_value,
        confidence=output.confidence,
        data_quality=output.data_quality.quality_score,
        as_of_date=output.as_of_date,
        parameter_version=output.parameter_version,
        model_version=output.model_version,
        reason_codes=_reason_items(output.reason_codes),
        warnings=_warning_items(output.warnings),
    )


def _bio_bottleneck_response(breakdown) -> BioCapexBottleneckScoreResponse:
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
        core_anchor_allowed=not any(reason.code == "BIO_CAPEX_CORE_ANCHOR_BLOCKED" for reason in breakdown.reason_codes),
        as_of_date=breakdown.as_of_date,
        parameter_version=breakdown.parameter_version,
        model_version=breakdown.model_version,
        reason_codes=_reason_items(breakdown.reason_codes),
        warnings=_warning_items(breakdown.warnings),
    )


def _ai_snapshot(adapter: CapexInputAdapter, decision_date: date) -> HistoricalSnapshot:
    capex_rows = _rows(adapter.fetch_series("ai.capex.yoy", as_of=_decision_time(decision_date)))
    token_rows = _rows(adapter.fetch_series("ai.token_proxy.growth", as_of=_decision_time(decision_date)))
    latest_capex = _latest(capex_rows)
    previous_capex = _previous(capex_rows)
    latest_token = _latest(token_rows)
    points: dict[str, RawDataPoint] = {}
    if latest_capex is not None:
        points["bigtech_ai_capex_yoy"] = _raw("bigtech_ai_capex_yoy", latest_capex.value, latest_capex)
        capex_accel = 0.0
        if previous_capex is not None and previous_capex.value is not None and latest_capex.value is not None:
            capex_accel = float(latest_capex.value) - float(previous_capex.value)
        points["bigtech_ai_capex_accel"] = _raw("bigtech_ai_capex_accel", capex_accel, latest_capex)
    if latest_token is not None and latest_token.value is not None:
        token_growth = float(latest_token.value)
        points["token_proxy_index"] = _raw("token_proxy_index", 1.0 + token_growth, latest_token)
        points["token_proxy_index_prev"] = _raw("token_proxy_index_prev", 1.0, latest_token)
    return HistoricalSnapshot("capex_cycle_feature_ai", decision_date, points)


def _bio_snapshot(
    capex_adapter: CapexInputAdapter,
    company_metric_adapter: CompanyMetricAdapter,
    decision_date: date,
) -> HistoricalSnapshot:
    capacity = _latest(_rows(capex_adapter.fetch_series("bio.capex.component.capacity_growth", as_of=_decision_time(decision_date))))
    backlog = _latest(_rows(capex_adapter.fetch_series("bio.capex.component.backlog_growth", as_of=_decision_time(decision_date))))
    segment = _latest(
        _rows(company_metric_adapter.fetch_metric("sample_bio_supplier", "segment_revenue_growth", as_of=_decision_time(decision_date)))
    )
    order = _latest(
        _rows(company_metric_adapter.fetch_metric("sample_bio_supplier", "order_backlog_growth", as_of=_decision_time(decision_date)))
    )
    points: dict[str, RawDataPoint] = {}
    for key in STRUCTURAL_MOAT_COMPONENTS:
        if capacity is not None:
            points[key] = _raw(key, capacity.value, capacity)
    for key in DEMAND_MOMENTUM_COMPONENTS:
        source = {"segment_growth": segment, "order_growth": order, "backlog_growth": backlog}.get(key, backlog)
        if source is not None:
            points[key] = _raw(key, source.value, source)
    for key in FINANCIAL_QUALITY_COMPONENTS:
        if capacity is not None:
            points[key] = _raw(key, capacity.value, capacity)
    for key in RISK_PENALTY_COMPONENTS:
        if backlog is not None:
            points[key] = _raw(key, max(0.0, 1.0 - float(backlog.value or 0.0)), backlog)
    return HistoricalSnapshot("capex_cycle_feature_bio", decision_date, points)


def _derive_ai_inputs(snapshot: HistoricalSnapshot) -> dict[str, float | None]:
    capex = snapshot.points.get("bigtech_ai_capex_yoy")
    accel = snapshot.points.get("bigtech_ai_capex_accel")
    token = snapshot.points.get("token_proxy_index")
    token_prev = snapshot.points.get("token_proxy_index_prev")
    token_change = None if token is None or token_prev is None else float(token.value or 0.0) - float(token_prev.value or 0.0)
    return {
        "tcr": None if token_change is None or token_prev is None else safe_ratio(token_change, abs(float(token_prev.value or 0.0))),
        "tce": None if token_change is None or capex is None else safe_ratio(token_change, abs(float(capex.value or 0.0))),
        "capex_acceleration": None if accel is None else float(accel.value or 0.0),
    }


def _rows(rows) -> tuple[TimeSeriesPoint, ...]:
    return tuple(sorted(rows, key=lambda item: (item.observation_date, item.available_at)))


def _latest(rows: tuple[TimeSeriesPoint, ...]) -> TimeSeriesPoint | None:
    return rows[-1] if rows else None


def _previous(rows: tuple[TimeSeriesPoint, ...]) -> TimeSeriesPoint | None:
    return rows[-2] if len(rows) >= 2 else None


def _raw(key: str, value, point: TimeSeriesPoint) -> RawDataPoint:
    return RawDataPoint(
        key=key,
        value=None if value is None else float(value),
        source=point.source,
        as_of_date=point.observation_date,
        available_at=point.available_at,
        updated_at=point.updated_at,
    )


def _decision_time(decision_date: date) -> datetime:
    return datetime.combine(decision_date, time.max, tzinfo=UTC)


def _reason_items(reasons: list[ReasonCode]) -> list[ReasonItem]:
    return [ReasonItem(code=reason.code, category=reason.category, detail=reason.detail) for reason in reasons]


def _warning_items(warnings: list[DecisionWarning]) -> list[WarningItem]:
    return [
        WarningItem(code=warning.code, severity=warning.severity, source=warning.source, message=warning.message)
        for warning in warnings
    ]
