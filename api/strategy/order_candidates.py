from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

from api.strategy.audit_layer import mask_account_identifier
from api.strategy.phase_engines import RebalanceResult


class OrderCandidateError(ValueError):
    pass


@dataclass(frozen=True)
class OrderCandidateValidation:
    passed: bool
    actionable: bool
    blocked: bool
    reason_codes: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class OrderCandidate:
    candidate_id: str
    account_label: str
    asset_id: str
    side: str
    quantity: float | None
    amount: float | None
    estimated_price: float | None
    estimated_value: float | None
    estimated_cost: float | None
    estimated_tax: float | None
    validation: OrderCandidateValidation
    review_required: bool
    reason_codes: list[str]
    warnings: list[str]
    data_snapshot_id: str
    parameter_version: str
    model_version: str
    source_decision_id: str
    non_executable: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("candidate_id", "account_label", "asset_id", "side", "data_snapshot_id", "parameter_version", "model_version", "source_decision_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise OrderCandidateError(f"{field_name} is required")
        if self.side not in {"BUY", "SELL", "REDUCE", "NO_ACTION"}:
            raise OrderCandidateError("candidate side must be review semantics, not a broker order enum")
        if not self.non_executable:
            raise OrderCandidateError("order candidates must be non-executable by default")

    def to_review_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["account_label"] = mask_account_identifier(self.account_label) or "****"
        data["explicit_non_execution_statement"] = "This is a user-review candidate and was not executed."
        return data


@dataclass(frozen=True)
class OrderCandidateBatch:
    batch_id: str
    as_of_date: date
    actionable_candidates: list[OrderCandidate]
    blocked_candidates: list[OrderCandidate]
    review_required_candidates: list[OrderCandidate]
    no_action_items: list[dict[str, Any]]
    non_execution: bool = True
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class UserReviewOutput:
    batch: OrderCandidateBatch
    generated_at: str
    non_execution_statement: str = "Generated candidates are for user review only and were not submitted to any broker."


@dataclass(frozen=True)
class CandidateContext:
    account_label: str
    cash_available: float
    current_weights: dict[str, float]
    prices: dict[str, float]
    data_snapshot_id: str
    parameter_version: str = "phase13_v1"
    model_version: str = "order_candidate_generation_v1"
    min_order_value: float = 0.0
    prohibited_assets: set[str] = field(default_factory=set)
    account_eligible_assets: set[str] = field(default_factory=set)
    risky_asset_limit_breached: bool = False


def generate_order_candidates_from_rebalance(
    results: list[RebalanceResult],
    context: CandidateContext,
) -> list[OrderCandidate]:
    output: list[OrderCandidate] = []
    for result in results:
        action = result.action_candidate.action
        if action in {"NO_ACTION", "HOLD_OVERWEIGHT_WINNER"}:
            continue
        side = "BUY" if action in {"BUY_CANDIDATE", "ADJUST_WITH_NEW_CASH"} else "SELL"
        price = context.prices.get(result.asset_id)
        amount = result.action_candidate.estimated_weight_change * 100_000.0
        quantity = None if price in {None, 0} else amount / float(price)
        validation = validate_candidate_inputs(
            asset_id=result.asset_id,
            side=side,
            amount=amount,
            price=price,
            context=context,
        )
        output.append(
            OrderCandidate(
                candidate_id=f"candidate:{result.asset_id}:{action}",
                account_label=context.account_label,
                asset_id=result.asset_id,
                side=side,
                quantity=quantity,
                amount=amount,
                estimated_price=price,
                estimated_value=None if price is None or quantity is None else price * quantity,
                estimated_cost=None if price is None else amount * 0.0005,
                estimated_tax=None,
                validation=validation,
                review_required=not validation.actionable,
                reason_codes=[*result.reason_codes, *validation.reason_codes],
                warnings=[*result.warnings, *validation.warnings],
                data_snapshot_id=context.data_snapshot_id,
                parameter_version=context.parameter_version,
                model_version=context.model_version,
                source_decision_id=f"rebalance:{result.asset_id}:{result.as_of_date.isoformat()}",
            )
        )
    return output


def validate_candidate_inputs(
    *,
    asset_id: str,
    side: str,
    amount: float,
    price: float | None,
    context: CandidateContext,
) -> OrderCandidateValidation:
    reasons: list[str] = []
    warnings: list[str] = []
    blocked = False
    if asset_id in context.prohibited_assets:
        blocked = True
        reasons.append("PROHIBITED_ASSET_BLOCKED")
    if context.account_eligible_assets and asset_id not in context.account_eligible_assets:
        blocked = True
        reasons.append("ACCOUNT_INELIGIBLE_ASSET_BLOCKED")
    if side == "BUY" and context.risky_asset_limit_breached:
        blocked = True
        reasons.append("RISKY_ASSET_LIMIT_BLOCKED")
    if side == "BUY" and amount > context.cash_available:
        blocked = True
        reasons.append("INSUFFICIENT_CASH_BLOCKED")
    if price is None or price <= 0:
        blocked = True
        warnings.append("MISSING_PRICE_BLOCKS_RISK_INCREASE")
    if amount < context.min_order_value:
        blocked = True
        reasons.append("MIN_ORDER_SIZE_BLOCKED")
    if not context.account_label:
        blocked = True
        warnings.append("MISSING_ACCOUNT_STATE_BLOCKS_RISK_INCREASE")
    if not blocked:
        reasons.append("ORDER_CANDIDATE_VALIDATED")
    return OrderCandidateValidation(not blocked, not blocked, blocked, reasons, warnings)


def build_user_review_output(candidates: list[OrderCandidate], *, batch_id: str, as_of_date: date, generated_at: str) -> UserReviewOutput:
    actionable = [candidate for candidate in candidates if candidate.validation.actionable and not candidate.review_required]
    blocked = [candidate for candidate in candidates if candidate.validation.blocked]
    review_required = [candidate for candidate in candidates if candidate.review_required and not candidate.validation.blocked]
    warnings = sorted({warning for candidate in candidates for warning in candidate.warnings})
    return UserReviewOutput(
        OrderCandidateBatch(
            batch_id=batch_id,
            as_of_date=as_of_date,
            actionable_candidates=actionable,
            blocked_candidates=blocked,
            review_required_candidates=review_required,
            no_action_items=[],
            warnings=warnings,
        ),
        generated_at=generated_at,
    )
