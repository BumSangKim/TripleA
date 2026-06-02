from __future__ import annotations

import copy
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from api.score_pipeline.adaptive import AdaptiveNormalizationConfig, AdaptiveNormalizationMethod, AdaptiveNormalizedValue
from api.score_pipeline.adaptive_normalization import AdaptiveNormalizationObservation, normalize_adaptive_feature
from api.score_pipeline.backtest import PipelineBacktestConfig, PipelineBacktestRunner, PortfolioState
from api.score_pipeline.contracts import DecisionLogRecord, ReasonCode
from api.score_pipeline.data_quality import HistoricalSnapshot, RawDataPoint, SnapshotBuilder
from api.score_pipeline.memory_cycle import (
    MemoryCycleCoverageStatus,
    MemoryCycleProxyPoint,
    evaluate_memory_cycle_coverage,
)
from api.score_pipeline.parameters import ParameterRegistry
from api.strategy.ai_capex_token_component import AICapexTokenDiagnosticComponent
from api.strategy.ai_capex_token_features import AICapexTokenFeatureBuilder
from api.strategy.ai_capex_token_input_adapter import AICapexTokenInputAdapter
from api.strategy.ai_capex_token_scenario_engine import AICapexTokenScenarioEngine


FIXTURE_PATH = Path("tests/fixtures/ai_capex_token/adaptive_input_to_score_path.json")
TEST_CONFIG = {
    "enabled": False,
    "diagnostic_only": True,
    "normalization_parameters": {"metadata": {"approved": True}},
    "scenario_probability_parameters": {"membership_strength": 0.8},
}
STANDARD_SCORE_FIELDS = {
    "score",
    "previous_score",
    "score_change",
    "confidence",
    "data_quality",
    "stability",
    "adjustment_intensity",
    "reason_codes",
    "as_of_date",
    "parameter_version",
    "model_version",
    "components",
}


def test_fixture_source_to_adaptive_score_and_backtest_output_path():
    fixture = _load_fixture()
    decision_date = date.fromisoformat(fixture["decision_date"])
    historical_snapshot = _historical_snapshot(fixture)

    assert historical_snapshot.get_available("token.current") is not None
    assert "future.probe" not in historical_snapshot.points
    assert any(warning.code == "FUTURE_DATA_REJECTED" for warning in historical_snapshot.warnings)

    payload = fixture["ai_capex_token_payload"]
    snapshot = AICapexTokenInputAdapter().adapt(payload)
    features = AICapexTokenFeatureBuilder().build(snapshot, config=TEST_CONFIG)
    adaptive_value = _adaptive_value(features.token_consumption_change or 0.0, decision_date)
    distribution = AICapexTokenScenarioEngine().evaluate(features, config=TEST_CONFIG)
    diagnostic = AICapexTokenDiagnosticComponent().build(payload, config=TEST_CONFIG)
    memory_report = _memory_report(fixture)
    backtest_result = _backtest(historical_snapshot)

    assert 0.0 <= adaptive_value.normalized_value <= 1.0
    assert adaptive_value.calibration_report.is_usable is True
    assert distribution.dominant_scenario_explanation_only is True
    assert diagnostic.applied_to_sector_engine is False
    assert memory_report.status == MemoryCycleCoverageStatus.PASS_TWO_OR_MORE_CYCLES
    assert memory_report.proxy_names_used == ("dram_asp_index",)
    assert "FUTURE_PROXY_POINTS_EXCLUDED" in memory_report.reason_codes
    assert backtest_result.parameter_version == "ai_capex_token_adaptive_tuning_v0"
    assert backtest_result.model_version == "score_pipeline_backtest_v1"
    assert backtest_result.decision_logs[-1].decision == "HOLD"
    assert backtest_result.decision_logs[-1].target_weights == backtest_result.decision_logs[-1].current_weights
    assert backtest_result.metrics["turnover"] == 0.0

    for component in diagnostic.components:
        score_payload = component.to_score_signal_dict()
        assert set(score_payload) == STANDARD_SCORE_FIELDS
        assert score_payload["parameter_version"]
        assert score_payload["model_version"]
        assert score_payload["reason_codes"]
        assert score_payload["components"][0]["contribution"] >= 0.0


def test_stale_data_reduces_quality_and_confidence_in_full_flow():
    payload = copy.deepcopy(_load_fixture()["ai_capex_token_payload"])
    baseline = AICapexTokenDiagnosticComponent().build(payload, config=TEST_CONFIG)
    payload["token_sources_current"][0]["quality_score"] = 0.4
    payload["token_sources_current"][0]["missing_ratio"] = 0.25
    payload["token_sources_current"][0]["is_stale"] = True

    stale = AICapexTokenDiagnosticComponent().build(payload, config=TEST_CONFIG)

    assert max(component.confidence for component in stale.components) < max(
        component.confidence for component in baseline.components
    )
    assert all(component.data_quality <= 0.4 for component in stale.components)


def test_missing_token_previous_cannot_increase_risk():
    payload = copy.deepcopy(_load_fixture()["ai_capex_token_payload"])
    payload["token_sources_previous"] = []

    result = AICapexTokenInputAdapter().adapt_with_metadata(payload)

    assert result.snapshot is None
    assert result.fallback_state == "REVIEW_REQUIRED"
    assert "MISSING_TOKEN_PREVIOUS_REVIEW_REQUIRED" in result.reason_codes


def test_missing_capex_t_minus_2_prevents_acceleration_and_falls_back():
    payload = copy.deepcopy(_load_fixture()["ai_capex_token_payload"])
    payload["capex_series"] = [row for row in payload["capex_series"] if row["period_role"] != "t_minus_2"]

    result = AICapexTokenInputAdapter().adapt_with_metadata(payload)

    assert result.snapshot is None
    assert result.fallback_state == "REVIEW_REQUIRED"
    assert "MISSING_CAPEX_PERIOD_REVIEW_REQUIRED" in result.reason_codes


def test_zero_diagnostic_contribution_does_not_alter_backtest_allocation():
    result = _backtest(_historical_snapshot(_load_fixture()))
    log = result.decision_logs[-1]

    assert log.rebalance_scores["ai_capex_token_contribution"] == 0.0
    assert log.target_weights == log.current_weights
    assert result.metrics["turnover"] == 0.0


def _load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _historical_snapshot(fixture: dict[str, Any]) -> HistoricalSnapshot:
    decision_date = date.fromisoformat(fixture["decision_date"])
    points = [
        RawDataPoint(
            key=row["key"],
            value=row["value"],
            source=row["source"],
            as_of_date=date.fromisoformat(row["as_of_date"]),
            available_at=datetime.fromisoformat(row["available_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            revision_id=row["revision_id"],
        )
        for row in fixture["raw_points"]
    ]
    return SnapshotBuilder().build(fixture["snapshot_id"], decision_date, points)


def _adaptive_value(raw_value: float, decision_date: date) -> AdaptiveNormalizedValue:
    config = AdaptiveNormalizationConfig(
        method=AdaptiveNormalizationMethod.ROLLING_PERCENTILE,
        lookback_periods=36,
        lookback_months=36,
        min_observations=24,
        parameter_version="ai_capex_token_adaptive_tuning_v0",
        model_version="ai_capex_token_adaptive_shadow_v0",
    )
    observations = []
    for index in range(24):
        year = 2024 + index // 12
        month = index % 12 + 1
        observed_on = date(year, month, 28)
        observations.append(
            AdaptiveNormalizationObservation(
                feature_name="token_delta",
                observed_on=observed_on,
                value=-0.03 + index * 0.01,
                available_at=datetime(year, month, 28, 0, 0, 0),
            )
        )
    return normalize_adaptive_feature(
        feature_name="token_delta",
        raw_value=raw_value,
        observations=observations,
        decision_date=decision_date,
        config=config,
        confidence=0.8,
        data_quality=0.95,
    )


def _memory_report(fixture: dict[str, Any]):
    points = [
        MemoryCycleProxyPoint(
            proxy_name=row["proxy_name"],
            observed_on=date.fromisoformat(row["observed_on"]),
            value=float(row["value"]),
            available_at=datetime.fromisoformat(row["available_at"]),
        )
        for row in fixture["memory_cycle_proxy_series"]
    ]
    return evaluate_memory_cycle_coverage(
        points,
        backtest_start=date(2024, 1, 31),
        backtest_end=date(2024, 6, 30),
        decision_date=date(2026, 2, 10),
        min_points=5,
    )


def _backtest(snapshot: HistoricalSnapshot):
    registry = ParameterRegistry.from_yaml()
    config = PipelineBacktestConfig(
        start_date=date(2026, 1, 10),
        end_date=snapshot.decision_date,
        frequency="monthly",
        initial_value=100_000.0,
        parameter_version="ai_capex_token_adaptive_tuning_v0",
    )
    return PipelineBacktestRunner(registry).run(config, [snapshot], _hold_pipeline)


def _hold_pipeline(
    snapshot: HistoricalSnapshot,
    state: PortfolioState,
    registry: ParameterRegistry,
) -> DecisionLogRecord:
    _ = registry
    return DecisionLogRecord(
        date=snapshot.decision_date,
        data_snapshot_id=snapshot.snapshot_id,
        parameter_version="ai_capex_token_adaptive_tuning_v0",
        model_version="ai_capex_token_adaptive_shadow_v0",
        macro_scores={"ai_capex_token": 0.0},
        sector_scores={"ai_capex_token_diagnostic": 0.0},
        risk_budget_scores={"diagnostic_only": 0.0},
        target_weights=dict(state.weights),
        current_weights=dict(state.weights),
        rebalance_scores={"ai_capex_token_contribution": 0.0},
        account_constraints={"simulation_only": True},
        decision="HOLD",
        adjustment_intensity=0.0,
        reason_codes=[ReasonCode("AI_CAPEX_TOKEN_DIAGNOSTIC_NO_ALLOCATION_CHANGE", "diagnostic")],
        warnings=list(snapshot.warnings),
    )
