from datetime import UTC, date, datetime, timedelta

from api.score_pipeline.audit import DecisionLogWriter, OrderCandidateGenerator, ReportingSummary, explain_decision
from api.score_pipeline.backtest import PipelineBacktestConfig, PipelineBacktestRunner, SimulationClock
from api.score_pipeline.contracts import (
    CandidateAction,
    ConstraintResult,
    DecisionLogRecord,
    DecisionWarning,
    ReasonCode,
    RebalancingDecision,
)
from api.score_pipeline.data_quality import RawDataPoint, SnapshotBuilder
from api.score_pipeline.parameters import ParameterRegistry


NOW = datetime(2026, 5, 27, tzinfo=UTC)


def _log(snapshot, state, registry):
    return DecisionLogRecord(
        date=snapshot.decision_date,
        data_snapshot_id=snapshot.snapshot_id,
        parameter_version=registry.parameter_version_for(["target_change_limit"], snapshot.decision_date),
        model_version="pipeline_test_v1",
        macro_scores={"neutral": 0.5},
        sector_scores={"SPY": 0.6},
        risk_budget_scores={"risk": 0.8},
        target_weights={"SPY": 0.10, "CASH": 0.90},
        current_weights=state.weights,
        rebalance_scores={"SPY": 0.2},
        account_constraints={"passed": True},
        decision="HOLD",
        adjustment_intensity=0.2,
        reason_codes=[ReasonCode("PIPELINE_CALLED", "backtest")],
        warnings=[],
    )


def _snapshot(day: date, snapshot_id: str):
    return SnapshotBuilder().build(
        snapshot_id,
        day,
        [RawDataPoint("price", 100, "fixture", day, datetime.combine(day, datetime.min.time(), tzinfo=UTC), NOW)],
    )


def test_simulation_clock_and_pipeline_called_per_rebalance_date():
    config = PipelineBacktestConfig(date(2026, 1, 1), date(2026, 3, 1), "monthly", 1000, "score_pipeline_v1")
    assert SimulationClock().dates(config) == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]
    result = PipelineBacktestRunner(ParameterRegistry.from_yaml()).run(
        config,
        [_snapshot(date(2026, 1, 1), "snap-1"), _snapshot(date(2026, 2, 1), "snap-2"), _snapshot(date(2026, 3, 1), "snap-3")],
        _log,
    )
    assert len(result.decision_logs) == 3
    assert result.metrics["turnover"] is not None
    assert result.metrics["cost_adjusted_return"] is not None


def test_no_future_data_leakage_fixture():
    future_point = RawDataPoint("price", 100, "fixture", date(2026, 5, 28), NOW + timedelta(days=1), NOW)
    snapshot = SnapshotBuilder().build("snap-future", date(2026, 5, 27), [future_point])
    assert "price" not in snapshot.points
    assert snapshot.warnings[0].code == "FUTURE_DATA_REJECTED"


def test_backtest_reproducibility_with_same_parameter_version():
    config = PipelineBacktestConfig(date(2026, 1, 1), date(2026, 2, 1), "monthly", 1000, "score_pipeline_v1")
    snapshots = [_snapshot(date(2026, 1, 1), "snap-1"), _snapshot(date(2026, 2, 1), "snap-2")]
    runner = PipelineBacktestRunner(ParameterRegistry.from_yaml())
    assert runner.run(config, snapshots, _log).equity_curve == runner.run(config, snapshots, _log).equity_curve


def test_missing_snapshot_conservative_fallback_warning():
    config = PipelineBacktestConfig(date(2026, 1, 1), date(2026, 2, 1), "monthly", 1000, "score_pipeline_v1")
    result = PipelineBacktestRunner(ParameterRegistry.from_yaml()).run(config, [_snapshot(date(2026, 1, 1), "snap-1")], _log)
    assert any(warning.code == "MISSING_BACKTEST_SNAPSHOT" for warning in result.warnings)


def test_decision_log_reporting_and_explanation_serialization():
    writer = DecisionLogWriter()
    record = writer.write(_log(_snapshot(date(2026, 1, 1), "snap-1"), type("State", (), {"weights": {}})(), ParameterRegistry.from_yaml()))
    summary = ReportingSummary().build(writer.records)
    explanation = explain_decision(record)
    assert "PIPELINE_CALLED" in summary["reason_codes"]
    assert explanation["data_snapshot_id"] == "snap-1"
    assert "PIPELINE_CALLED" in summary["records_json"][0]


def test_order_candidate_generation_review_only_and_blocked_constraint():
    decision = RebalancingDecision(
        asset_id="SPY",
        action=CandidateAction.BUY,
        intensity=0.5,
        target_weight=0.15,
        current_weight=0.10,
        score=0.7,
        previous_score=0.6,
        score_change=0.1,
        confidence=0.8,
        data_quality=0.9,
        stability=0.9,
        adjustment_intensity=0.5,
        as_of_date=date(2026, 5, 27),
        parameter_version="score_pipeline_v1",
        model_version="rebalance_v1",
        reason_codes=[ReasonCode("BUY_CANDIDATE_FROM_SCORE_FLOW", "order_candidate")],
        warnings=[],
    )
    passed = ConstraintResult(True, False)
    candidate = OrderCandidateGenerator().generate(account_id="acct-1", decision=decision, constraint_result=passed, price=100, portfolio_value=10000, as_of_date=date(2026, 5, 27))
    blocked = OrderCandidateGenerator().generate(
        account_id="acct-1",
        decision=decision,
        constraint_result=ConstraintResult(False, True, [ReasonCode("ACCOUNT_NOT_ELIGIBLE", "constraint")]),
        price=100,
        portfolio_value=10000,
        as_of_date=date(2026, 5, 27),
    )
    assert candidate.requires_user_review is True
    assert candidate.execution_allowed is False
    assert candidate.action_candidate == CandidateAction.BUY
    assert blocked.action_candidate == CandidateAction.BLOCKED


def test_no_broker_order_api_call_shape():
    candidate = OrderCandidateGenerator().generate(
        account_id="acct-1",
        decision=RebalancingDecision(
            "SPY",
            CandidateAction.HOLD,
            0.1,
            0.1,
            0.1,
            0.5,
            None,
            0.0,
            1.0,
            1.0,
            1.0,
            0.1,
            date(2026, 5, 27),
            "p",
            "m",
        ),
        constraint_result=ConstraintResult(True, False),
        price=None,
        portfolio_value=10000,
        as_of_date=date(2026, 5, 27),
    )
    assert not hasattr(candidate, "broker_order_payload")
    assert candidate.execution_allowed is False
