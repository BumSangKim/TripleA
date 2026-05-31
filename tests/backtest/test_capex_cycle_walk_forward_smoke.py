from __future__ import annotations

import math
import sys
from datetime import UTC, date, datetime, time, timedelta

from api.data.adapters.fixtures import FixtureCapexInputAdapter
from api.score_pipeline.backtest import PipelineBacktestConfig, PipelineBacktestRunner
from api.score_pipeline.contracts import DecisionLogRecord, ReasonCode
from api.score_pipeline.data_quality import HistoricalSnapshot, RawDataPoint
from api.score_pipeline.parameters import ParameterEntry, ParameterRegistry
from api.score_pipeline.plugins.ai_capex_cycle import AICapexCyclePlugin
from api.score_pipeline.plugins.capex_common import safe_ratio
from api.score_pipeline.plugins.capex_scenario import CapexScenarioEngine
from api.score_pipeline.plugins.valuation_engine import PERBounds, ValuationEngine


DECISION_DATES = (date(2026, 5, 31), date(2026, 8, 1))


def test_capex_cycle_walk_forward_smoke_is_deterministic_and_readonly():
    loaded_before = set(sys.modules)
    registry = _registry()
    snapshots = [_snapshot(day) for day in DECISION_DATES]
    config = PipelineBacktestConfig(DECISION_DATES[0], DECISION_DATES[1], "monthly", 100_000, "capex_walk_forward_test_v1")
    runner = PipelineBacktestRunner(registry)

    first = runner.run(config, snapshots, _capex_pipeline)
    second = runner.run(config, snapshots, _capex_pipeline)

    assert first.equity_curve == second.equity_curve
    assert [log.data_snapshot_id for log in first.decision_logs] == [snapshot.snapshot_id for snapshot in snapshots]
    assert len(first.decision_logs) == len(snapshots)
    for log in first.decision_logs:
        assert math.isfinite(log.sector_scores["ai_capex_cycle"])
        assert log.parameter_version
        assert log.model_version == "capex_walk_forward_smoke_v1"
        assert any(reason.code == "AI_CAPEX_CYCLE_COMPUTED" for reason in log.reason_codes)
        assert any(reason.code == "CAPEX_WALK_FORWARD_SMOKE" for reason in log.reason_codes)
        assert log.decision == "HOLD"
        assert log.target_weights == {"CASH": 1.0}
        assert log.account_constraints["execution_allowed"] is False
    assert first.metrics["turnover"] is not None
    assert math.isfinite(first.metrics["turnover"])
    assert _new_forbidden_runtime_modules(loaded_before) == []


def _capex_pipeline(snapshot, state, registry) -> DecisionLogRecord:
    ai_output = AICapexCyclePlugin().compute(snapshot, registry)
    inputs = _scenario_inputs(snapshot)
    scenario = CapexScenarioEngine().evaluate(
        as_of_date=snapshot.decision_date,
        ai_capex_cycle_score=ai_output.normalized_value,
        tcr=inputs["tcr"],
        tce=inputs["tce"],
        capex_acceleration=inputs["capex_acceleration"],
        macro_multiplier=1.0,
        data_quality=ai_output.data_quality.quality_score,
    )
    valuation = ValuationEngine().evaluate(
        asset_id="fixture_ai_infrastructure",
        as_of_date=snapshot.decision_date,
        forward_eps=None,
        midcycle_eps=1.0,
        base_per=20.0,
        last_price=30.0,
        macro_multiplier=1.0,
        per_bounds=PERBounds(min_per=10.0, max_per=30.0),
        confidence=ai_output.confidence,
        data_quality=ai_output.data_quality.quality_score,
    )
    return DecisionLogRecord(
        date=snapshot.decision_date,
        data_snapshot_id=snapshot.snapshot_id,
        parameter_version=ai_output.parameter_version,
        model_version="capex_walk_forward_smoke_v1",
        macro_scores={"capex_scenario": scenario.distribution},
        sector_scores={"ai_capex_cycle": ai_output.normalized_value},
        risk_budget_scores={},
        target_weights={"CASH": 1.0},
        current_weights=state.weights,
        rebalance_scores={},
        account_constraints={"execution_allowed": False},
        decision="HOLD",
        adjustment_intensity=0.0,
        reason_codes=[
            *ai_output.reason_codes,
            *scenario.reason_codes,
            *valuation.reason_codes,
            ReasonCode("CAPEX_WALK_FORWARD_SMOKE", "backtest"),
        ],
        warnings=[*ai_output.warnings, *scenario.warnings, *valuation.warnings],
    )


def _snapshot(day: date) -> HistoricalSnapshot:
    adapter = FixtureCapexInputAdapter()
    decision_time = datetime.combine(day, time.max, tzinfo=UTC)
    capex_rows = adapter.fetch_series("ai.capex.yoy", as_of=decision_time)
    token_rows = adapter.fetch_series("ai.token_proxy.growth", as_of=decision_time)
    capex_latest = capex_rows[-1]
    capex_previous = capex_rows[-2] if len(capex_rows) >= 2 else None
    token_latest = token_rows[-1]
    capex_acceleration = 0.0 if capex_previous is None else float(capex_latest.value) - float(capex_previous.value)
    points = [
        _point("bigtech_ai_capex_yoy", float(capex_latest.value), capex_latest.observation_date, capex_latest.available_at),
        _point("bigtech_ai_capex_accel", capex_acceleration, capex_latest.observation_date, capex_latest.available_at),
        _point("token_proxy_index", 1.0 + float(token_latest.value), token_latest.observation_date, token_latest.available_at),
        _point("token_proxy_index_prev", 1.0, token_latest.observation_date, token_latest.available_at),
    ]
    return HistoricalSnapshot(f"capex-fixture-{day.isoformat()}", day, {point.key: point for point in points})


def _point(key: str, value: float, as_of_date: date, available_at: datetime) -> RawDataPoint:
    return RawDataPoint(
        key=key,
        value=value,
        source="capex_fixture",
        as_of_date=as_of_date,
        available_at=available_at,
        updated_at=available_at,
    )


def _scenario_inputs(snapshot: HistoricalSnapshot) -> dict[str, float]:
    capex = snapshot.points["bigtech_ai_capex_yoy"]
    acceleration = snapshot.points["bigtech_ai_capex_accel"]
    token = snapshot.points["token_proxy_index"]
    previous = snapshot.points["token_proxy_index_prev"]
    token_change = float(token.value) - float(previous.value)
    return {
        "tcr": safe_ratio(token_change, abs(float(previous.value))),
        "tce": safe_ratio(token_change, abs(float(capex.value))),
        "capex_acceleration": float(acceleration.value),
    }


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
            _entry("transaction_cost_bps", 0.0),
        ]
    )


def _entry(name: str, value) -> ParameterEntry:
    return ParameterEntry(
        name=name,
        value=value,
        version="capex_walk_forward_test_v1",
        valid_from=DECISION_DATES[0] - timedelta(days=365),
        valid_to=None,
        source="test",
        reason="walk-forward smoke fixture",
        approved=True,
        affected_modules=["score_pipeline"],
    )


def _new_forbidden_runtime_modules(loaded_before: set[str]) -> list[str]:
    prefixes = ("api.brokers", "api.features.orders", "api.strategy")
    return sorted(name for name in set(sys.modules) - loaded_before if name.startswith(prefixes))
