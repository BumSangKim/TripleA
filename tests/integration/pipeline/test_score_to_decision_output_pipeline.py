from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime

from api.score_pipeline.audit import DecisionLogWriter, OrderCandidateGenerator, ReportingSummary, explain_decision
from api.score_pipeline.contracts import CandidateAction, DecisionLogRecord, ReasonCode
from api.score_pipeline.data_quality import RawDataPoint, SnapshotBuilder
from api.score_pipeline.engines import (
    AllocationEngine,
    MacroRegimeEngine,
    RebalancingEngine,
    RiskBudgetEngine,
    SectorDefinition,
    SectorScoringEngine,
)
from api.score_pipeline.features import FeatureRegistry, PriceMomentumFeaturePlugin
from api.score_pipeline.parameters import ParameterRegistry
from api.score_pipeline.scoring import ScoreRegistry


def test_score_to_decision_output_flow_preserves_contracts(
    sample_raw_data: dict,
    sample_account_state: dict,
    sample_current_positions: dict,
) -> None:
    context = _build_decision_context(sample_raw_data, sample_account_state, sample_current_positions)

    assert context["macro"].distribution
    assert abs(sum(context["macro"].distribution.values()) - 1.0) < 0.000001
    assert context["macro"].dominant_regime_explanation_only is True

    target = context["target"]
    assert target.min_weight <= target.base_weight <= target.max_weight
    assert target.min_weight <= target.current_target <= target.max_weight

    rebalance = context["rebalance"]
    assert rebalance.action
    assert 0 <= rebalance.intensity <= 1

    candidate = context["candidate"]
    assert candidate.requires_user_review is True
    assert candidate.execution_allowed is False
    assert candidate.action_candidate in CandidateAction.values()

    audit_payload = asdict(context["decision_log"])
    for field_name in ("data_snapshot_id", "parameter_version", "model_version", "reason_codes", "warnings", "date"):
        assert field_name in audit_payload

    explanation = explain_decision(context["decision_log"])
    assert explanation["data_snapshot_id"] == "pipeline-fixture:score-to-decision"
    assert explanation["reason_codes"]


def test_hard_constraint_blocks_before_order_candidate_generation(
    sample_raw_data: dict,
    sample_account_state: dict,
    sample_current_positions: dict,
) -> None:
    context = _build_decision_context(
        sample_raw_data,
        sample_account_state,
        sample_current_positions,
        risky_weight_override=0.95,
    )

    assert context["risk"].constraint_result.blocked is True
    assert context["candidate"].constraint_result.blocked is True
    assert context["candidate"].action_candidate == CandidateAction.BLOCKED
    assert context["candidate"].execution_allowed is False


def test_default_output_is_manual_review_required(sample_raw_data: dict, sample_account_state: dict, sample_current_positions: dict) -> None:
    context = _build_decision_context(sample_raw_data, sample_account_state, sample_current_positions)

    assert context["candidate"].requires_user_review is True
    assert context["candidate"].execution_allowed is False


def test_audit_summary_contains_reason_codes_warnings_and_versions(
    sample_raw_data: dict,
    sample_account_state: dict,
    sample_current_positions: dict,
) -> None:
    context = _build_decision_context(sample_raw_data, sample_account_state, sample_current_positions)
    writer = DecisionLogWriter()
    writer.write(context["decision_log"])
    summary = ReportingSummary().build(writer.records)

    assert summary["decision_count"] == 1
    assert summary["reason_codes"]
    assert "score_pipeline_order_candidate_v1" in summary["records_json"][0]
    assert context["decision_log"].parameter_version
    assert context["decision_log"].model_version


def test_poor_data_quality_does_not_create_risk_increasing_candidate(
    sample_raw_data: dict,
    sample_account_state: dict,
    sample_current_positions: dict,
) -> None:
    context = _build_decision_context(
        sample_raw_data,
        sample_account_state,
        sample_current_positions,
        data_quality_override=0.2,
    )

    assert context["risk"].risk_capacity == 0
    assert context["candidate"].action_candidate in {CandidateAction.BLOCKED, CandidateAction.REVIEW_REQUIRED, CandidateAction.HOLD}
    assert context["candidate"].action_candidate != CandidateAction.BUY


def _build_decision_context(
    sample_raw_data: dict,
    sample_account_state: dict,
    sample_current_positions: dict,
    *,
    risky_weight_override: float | None = None,
    data_quality_override: float | None = None,
) -> dict:
    registry = ParameterRegistry.from_yaml()
    as_of_date = date.fromisoformat(sample_raw_data["decision_date"])
    scores = _scores_from_fixture(sample_raw_data, registry)
    macro = MacroRegimeEngine().evaluate(scores, registry, as_of_date=as_of_date)
    sector_score = SectorScoringEngine(
        {
            "SAMPLE_SECTOR": SectorDefinition(
                sector_id="SAMPLE_SECTOR",
                enabled=True,
                component_weights={"macro_fit": 0.5, "data_quality": 0.5},
            )
        }
    ).score(
        sector_id="SAMPLE_SECTOR",
        macro=macro,
        components={},
        as_of_date=as_of_date,
        registry=registry,
        previous_score=0.45,
    )
    account = next(item for item in sample_account_state["accounts"] if item["account_type"] == "IRP")
    current_weight = _position_weight(sample_current_positions, account["account_id"], "SAMPLE_US_EQUITY")
    risky_weight = risky_weight_override if risky_weight_override is not None else current_weight
    risk = RiskBudgetEngine().evaluate(
        account_type="irp",
        current_weights={"SAMPLE_US_EQUITY": risky_weight},
        risky_assets={"SAMPLE_US_EQUITY"},
        volatility=0.10,
        drawdown=0.05,
        data_quality=data_quality_override if data_quality_override is not None else sector_score.data_quality,
        registry=registry,
        as_of_date=as_of_date,
    )
    target = AllocationEngine().allocate(
        asset_id="SAMPLE_US_EQUITY",
        sector_score=sector_score,
        macro=macro,
        risk=risk,
        previous_target=current_weight,
        registry=registry,
    )
    rebalance = RebalancingEngine().decide(
        target=target,
        current_weight=current_weight,
        sector_score=sector_score,
        risk=risk,
        cash_available_score=0.5,
        turnover_penalty=0.1,
    )
    candidate = OrderCandidateGenerator().generate(
        account_id=account["account_id"],
        decision=rebalance,
        constraint_result=risk.constraint_result,
        price=100.0,
        portfolio_value=float(account["holdings_summary"]["market_value"]),
        as_of_date=as_of_date,
    )
    decision_log = DecisionLogRecord(
        date=as_of_date,
        data_snapshot_id="pipeline-fixture:score-to-decision",
        parameter_version=candidate.parameter_version,
        model_version=candidate.model_version,
        macro_scores=macro.distribution,
        sector_scores={sector_score.sector_id: sector_score.total_score},
        risk_budget_scores={"risk_capacity": risk.risk_capacity},
        target_weights={target.asset_id: target.current_target},
        current_weights={target.asset_id: current_weight},
        rebalance_scores={target.asset_id: rebalance.intensity},
        account_constraints={"blocked": risk.constraint_result.blocked},
        decision=candidate.action_candidate,
        adjustment_intensity=rebalance.adjustment_intensity,
        reason_codes=[ReasonCode("PIPELINE_E2E_DECISION_RECORDED", "audit"), *candidate.reason_codes],
        warnings=[*candidate.warnings, *risk.warnings],
    )
    return {
        "macro": macro,
        "sector_score": sector_score,
        "risk": risk,
        "target": target,
        "rebalance": rebalance,
        "candidate": candidate,
        "decision_log": decision_log,
    }


def _scores_from_fixture(sample_raw_data: dict, registry: ParameterRegistry):
    return [ScoreRegistry().calculate_all(_feature_outputs(sample_raw_data), registry)[0]]


def _feature_outputs(sample_raw_data: dict):
    decision_date = date.fromisoformat(sample_raw_data["decision_date"])
    snapshot = SnapshotBuilder().build(
        "pipeline-fixture:raw",
        decision_date,
        _raw_points_from_fixture(sample_raw_data),
    )
    registry = FeatureRegistry()
    registry.register(PriceMomentumFeaturePlugin(asset_id="SAMPLE_US_EQUITY"))
    return registry.run_enabled(snapshot, ParameterRegistry.from_yaml())


def _raw_points_from_fixture(sample_raw_data: dict) -> list[RawDataPoint]:
    points: list[RawDataPoint] = []
    price_row: dict | None = None
    for row in sample_raw_data["rows"]:
        available_at = datetime.fromisoformat(row["available_at"])
        points.append(
            RawDataPoint(
                key=f"{row['kind']}:{row['metric']}",
                value=float(row["value"]),
                source=row["source"],
                as_of_date=date.fromisoformat(row["as_of_date"]),
                available_at=available_at,
                updated_at=available_at,
            )
        )
        if row["kind"] == "price":
            price_row = row

    assert price_row is not None
    price_available_at = datetime.fromisoformat(price_row["available_at"])
    for key in ("price_start", "price_end"):
        points.append(
            RawDataPoint(
                key=key,
                value=float(price_row["value"]),
                source=price_row["source"],
                as_of_date=date.fromisoformat(price_row["as_of_date"]),
                available_at=price_available_at,
                updated_at=price_available_at,
            )
        )
    return points


def _position_weight(sample_current_positions: dict, account_id: str, asset_id: str) -> float:
    for position in sample_current_positions["positions"]:
        if position["account_id"] == account_id and position["asset_id"] == asset_id:
            return float(position["current_weight"])
    return 0.0
