from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import pytest

from api.data.adapters.fixtures import FixtureCapexInputAdapter
from api.data.adapters.ports import TimeSeriesPoint
from api.score_pipeline.data_quality import HistoricalSnapshot, RawDataPoint
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
DECISION_TIME = datetime.combine(DECISION_DATE, time.max, tzinfo=UTC)
CURRENT_AVAILABLE = datetime(2026, 5, 30, tzinfo=UTC)
FUTURE_AVAILABLE = datetime(2026, 6, 2, tzinfo=UTC)


def test_future_fixture_row_does_not_change_ai_score_or_scenario():
    baseline_snapshot = _ai_snapshot(_adapter_with_future_rows(include_future=False))
    future_snapshot = _ai_snapshot(_adapter_with_future_rows(include_future=True))
    registry = _registry()

    baseline_score = AICapexCyclePlugin().compute(baseline_snapshot, registry)
    future_score = AICapexCyclePlugin().compute(future_snapshot, registry)
    baseline_scenario = _scenario(baseline_snapshot, baseline_score.normalized_value)
    future_scenario = _scenario(future_snapshot, future_score.normalized_value)

    assert future_snapshot.points["bigtech_ai_capex_yoy"].value == baseline_snapshot.points["bigtech_ai_capex_yoy"].value
    assert future_score.normalized_value == pytest.approx(baseline_score.normalized_value)
    assert future_scenario.distribution == pytest.approx(baseline_scenario.distribution)


def test_future_ai_point_inside_snapshot_produces_blocker_metadata():
    snapshot = _ai_snapshot(_adapter_with_future_rows(include_future=False))
    current = snapshot.points["token_proxy_index"]
    snapshot.points["token_proxy_index"] = RawDataPoint(
        key=current.key,
        value=999.0,
        source=current.source,
        as_of_date=current.as_of_date,
        available_at=FUTURE_AVAILABLE,
        updated_at=FUTURE_AVAILABLE,
    )

    output = AICapexCyclePlugin().compute(snapshot, _registry())

    assert output.normalized_value == pytest.approx(0.5)
    assert output.confidence == 0.0
    assert any(warning.code == "AI_CAPEX_FUTURE_DATA_REJECTED" for warning in output.warnings)


def test_future_bio_component_matches_missing_input_and_records_warning():
    baseline_points = _bio_points()
    baseline_points.pop("switching_cost")
    future_points = dict(baseline_points)
    future_points["switching_cost"] = _raw("switching_cost", 1.0, FUTURE_AVAILABLE)
    registry = _registry()

    baseline = BioCapexBottleneckPlugin().compute_breakdown(
        HistoricalSnapshot("bio-baseline", DECISION_DATE, baseline_points),
        registry,
    )
    with_future = BioCapexBottleneckPlugin().compute_breakdown(
        HistoricalSnapshot("bio-future", DECISION_DATE, future_points),
        registry,
    )

    assert with_future.final_score == pytest.approx(baseline.final_score)
    assert any(warning.code == "BIO_CAPEX_FUTURE_DATA_REJECTED" for warning in with_future.warnings)


def test_future_valuation_input_is_excluded_before_engine_call():
    current_eps = TimeSeriesPoint(
        series_id="valuation.forward_eps",
        value=1.2,
        observation_date=DECISION_DATE,
        available_at=CURRENT_AVAILABLE,
        updated_at=CURRENT_AVAILABLE,
        source="fixture",
    )
    future_eps = TimeSeriesPoint(
        series_id="valuation.forward_eps",
        value=99.0,
        observation_date=DECISION_DATE + timedelta(days=1),
        available_at=FUTURE_AVAILABLE,
        updated_at=FUTURE_AVAILABLE,
        source="fixture",
    )

    selected = _latest_available([current_eps, future_eps], DECISION_TIME)
    result = ValuationEngine().evaluate(
        asset_id="fixture_ai",
        as_of_date=DECISION_DATE,
        forward_eps=float(selected.value),
        midcycle_eps=1.0,
        base_per=20.0,
        last_price=30.0,
        macro_multiplier=1.0,
        per_bounds=PERBounds(min_per=10.0, max_per=30.0),
    )

    assert selected.value == 1.2
    assert result.forward_eps == 1.2
    assert result.fair_value is not None
    assert result.fair_value < 99.0 * 30.0


def _adapter_with_future_rows(*, include_future: bool) -> FixtureCapexInputAdapter:
    capex_rows = [
        _point("ai.capex.yoy", 0.18, date(2026, 3, 31), CURRENT_AVAILABLE),
    ]
    token_rows = [
        _point("ai.token_proxy.growth", 0.34, date(2026, 3, 31), CURRENT_AVAILABLE),
    ]
    if include_future:
        capex_rows.append(_point("ai.capex.yoy", 9.99, date(2026, 6, 30), FUTURE_AVAILABLE))
        token_rows.append(_point("ai.token_proxy.growth", 9.99, date(2026, 6, 30), FUTURE_AVAILABLE))
    return FixtureCapexInputAdapter(
        {
            "ai.capex.yoy": tuple(capex_rows),
            "ai.token_proxy.growth": tuple(token_rows),
        }
    )


def _ai_snapshot(adapter: FixtureCapexInputAdapter) -> HistoricalSnapshot:
    capex = adapter.fetch_series("ai.capex.yoy", as_of=DECISION_TIME)[-1]
    token = adapter.fetch_series("ai.token_proxy.growth", as_of=DECISION_TIME)[-1]
    points = {
        "bigtech_ai_capex_yoy": _raw("bigtech_ai_capex_yoy", float(capex.value), capex.available_at),
        "bigtech_ai_capex_accel": _raw("bigtech_ai_capex_accel", 0.0, capex.available_at),
        "token_proxy_index": _raw("token_proxy_index", 1.0 + float(token.value), token.available_at),
        "token_proxy_index_prev": _raw("token_proxy_index_prev", 1.0, token.available_at),
    }
    return HistoricalSnapshot("ai-leakage", DECISION_DATE, points)


def _scenario(snapshot: HistoricalSnapshot, ai_score: float):
    capex = snapshot.points["bigtech_ai_capex_yoy"]
    acceleration = snapshot.points["bigtech_ai_capex_accel"]
    token = snapshot.points["token_proxy_index"]
    previous = snapshot.points["token_proxy_index_prev"]
    token_change = float(token.value) - float(previous.value)
    return CapexScenarioEngine().evaluate(
        as_of_date=DECISION_DATE,
        ai_capex_cycle_score=ai_score,
        tcr=safe_ratio(token_change, abs(float(previous.value))),
        tce=safe_ratio(token_change, abs(float(capex.value))),
        capex_acceleration=float(acceleration.value),
        macro_multiplier=1.0,
        data_quality=1.0,
    )


def _bio_points() -> dict[str, RawDataPoint]:
    points: dict[str, RawDataPoint] = {}
    for key in STRUCTURAL_MOAT_COMPONENTS:
        points[key] = _raw(key, 0.7, CURRENT_AVAILABLE)
    for key in DEMAND_MOMENTUM_COMPONENTS:
        points[key] = _raw(key, 0.6, CURRENT_AVAILABLE)
    for key in FINANCIAL_QUALITY_COMPONENTS:
        points[key] = _raw(key, 0.65, CURRENT_AVAILABLE)
    for key in RISK_PENALTY_COMPONENTS:
        points[key] = _raw(key, 0.2, CURRENT_AVAILABLE)
    return points


def _point(series_id: str, value: float, observed: date, available_at: datetime) -> TimeSeriesPoint:
    return TimeSeriesPoint(
        series_id=series_id,
        value=value,
        observation_date=observed,
        available_at=available_at,
        updated_at=available_at,
        source="leakage_fixture",
    )


def _raw(key: str, value: float, available_at: datetime) -> RawDataPoint:
    return RawDataPoint(key, value, "leakage_fixture", DECISION_DATE, available_at, available_at)


def _latest_available(rows: list[TimeSeriesPoint], decision_time: datetime) -> TimeSeriesPoint:
    return sorted([row for row in rows if row.available_at <= decision_time], key=lambda row: row.available_at)[-1]


def _registry() -> ParameterRegistry:
    return ParameterRegistry(
        [
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
            _entry(
                "final_score_weights",
                {
                    "structural_moat": 0.40,
                    "demand_momentum": 0.35,
                    "financial_quality": 0.25,
                    "risk_penalty_multiplier": 0.35,
                },
            ),
            _entry("structural_moat_weights", {key: 1.0 / len(STRUCTURAL_MOAT_COMPONENTS) for key in STRUCTURAL_MOAT_COMPONENTS}),
            _entry("demand_momentum_weights", {key: 1.0 / len(DEMAND_MOMENTUM_COMPONENTS) for key in DEMAND_MOMENTUM_COMPONENTS}),
            _entry("financial_quality_weights", {key: 1.0 / len(FINANCIAL_QUALITY_COMPONENTS) for key in FINANCIAL_QUALITY_COMPONENTS}),
            _entry("risk_penalty_weights", {key: 1.0 / len(RISK_PENALTY_COMPONENTS) for key in RISK_PENALTY_COMPONENTS}),
        ]
    )


def _entry(name: str, value) -> ParameterEntry:
    return ParameterEntry(
        name=name,
        value=value,
        version="capex_leakage_test_v1",
        valid_from=DECISION_DATE - timedelta(days=365),
        valid_to=None,
        source="test",
        reason="future leakage guard fixture",
        approved=True,
        affected_modules=["score_pipeline"],
    )
