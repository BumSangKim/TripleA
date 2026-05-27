from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from api.score_pipeline.contracts import (
    CandidateAction,
    ConstraintResult,
    DecisionLogRecord,
    DecisionWarning,
    OrderCandidate,
    ReasonCode,
    RebalancingDecision,
    to_json,
)


class DecisionLogWriter:
    def __init__(self):
        self.records: list[DecisionLogRecord] = []

    def write(self, record: DecisionLogRecord) -> DecisionLogRecord:
        self.records.append(record)
        return record

    def serialize(self) -> list[dict[str, Any]]:
        return [asdict(record) for record in self.records]


class ReportingSummary:
    def build(self, records: list[DecisionLogRecord]) -> dict[str, Any]:
        warnings = [warning.code for record in records for warning in record.warnings]
        reasons = [reason.code for record in records for reason in record.reason_codes]
        return {
            "decision_count": len(records),
            "reason_codes": sorted(set(reasons)),
            "warnings": sorted(set(warnings)),
            "records_json": [to_json(record) for record in records],
        }


class OrderCandidateGenerator:
    def generate(
        self,
        *,
        account_id: str,
        decision: RebalancingDecision,
        constraint_result: ConstraintResult,
        price: float | None,
        portfolio_value: float,
        as_of_date: date,
    ) -> OrderCandidate:
        if constraint_result.blocked:
            action = CandidateAction.BLOCKED
        elif decision.action in {CandidateAction.BUY, "LIMITED_INCREASE"}:
            action = CandidateAction.BUY
        elif decision.action in {CandidateAction.REDUCE, CandidateAction.SELL, "RISK_REDUCE_ONLY"}:
            action = CandidateAction.REDUCE
        elif decision.action == CandidateAction.HOLD or decision.action == "STOP_NEW_BUYS":
            action = CandidateAction.HOLD
        else:
            action = CandidateAction.REVIEW_REQUIRED
        estimated_amount = abs(decision.target_weight - decision.current_weight) * portfolio_value
        quantity = None if not price or price <= 0 else estimated_amount / price
        warnings = list(decision.warnings)
        reasons = [*decision.reason_codes, *constraint_result.reason_codes]
        if price is None and action in {CandidateAction.BUY, CandidateAction.REDUCE, CandidateAction.SELL}:
            warnings.append(DecisionWarning("MISSING_PRICE_REVIEW_REQUIRED", "WARNING", "order_candidate", decision.asset_id))
            action = CandidateAction.REVIEW_REQUIRED
        return OrderCandidate(
            candidate_id=f"candidate:{decision.asset_id}:{as_of_date.isoformat()}",
            account_id=account_id,
            asset_id=decision.asset_id,
            action_candidate=action,
            target_weight=decision.target_weight,
            current_weight=decision.current_weight,
            target_quantity_estimate=quantity,
            estimated_amount=estimated_amount,
            cash_impact=-estimated_amount if action == CandidateAction.BUY else estimated_amount,
            constraint_result=constraint_result,
            reason_codes=reasons,
            warnings=warnings,
            requires_user_review=True,
            execution_allowed=False,
            as_of_date=as_of_date,
            parameter_version=decision.parameter_version,
            model_version="score_pipeline_order_candidate_v1",
        )


def explain_decision(record: DecisionLogRecord) -> dict[str, Any]:
    return {
        "decision": record.decision,
        "data_snapshot_id": record.data_snapshot_id,
        "parameter_version": record.parameter_version,
        "model_version": record.model_version,
        "reason_codes": [reason.code for reason in record.reason_codes],
        "warnings": [warning.code for warning in record.warnings],
        "target_weights": record.target_weights,
        "account_constraints": record.account_constraints,
    }
