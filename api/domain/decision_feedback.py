from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping


class FeedbackContractError(ValueError):
    pass


class FeedbackSeverity:
    INFO = "INFO"
    WARNING = "WARNING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REDUCE_ONLY = "REDUCE_ONLY"
    BLOCK = "BLOCK"

    @classmethod
    def values(cls) -> set[str]:
        return {cls.INFO, cls.WARNING, cls.REVIEW_REQUIRED, cls.REDUCE_ONLY, cls.BLOCK}


class FeedbackTiming:
    SAME_RUN_REFINEMENT = "SAME_RUN_REFINEMENT"
    NEXT_RUN_INPUT = "NEXT_RUN_INPUT"
    PARAMETER_REVIEW = "PARAMETER_REVIEW"
    AUDIT_ONLY = "AUDIT_ONLY"

    @classmethod
    def values(cls) -> set[str]:
        return {cls.SAME_RUN_REFINEMENT, cls.NEXT_RUN_INPUT, cls.PARAMETER_REVIEW, cls.AUDIT_ONLY}


class FeedbackSourceLayer:
    DATA_QUALITY = "DATA_QUALITY"
    RISK_BUDGET = "RISK_BUDGET"
    REBALANCING = "REBALANCING"
    ACCOUNT_CONSTRAINT = "ACCOUNT_CONSTRAINT"
    ORDER_CANDIDATE = "ORDER_CANDIDATE"
    BACKTEST = "BACKTEST"
    AUDIT = "AUDIT"

    @classmethod
    def values(cls) -> set[str]:
        return {
            cls.DATA_QUALITY,
            cls.RISK_BUDGET,
            cls.REBALANCING,
            cls.ACCOUNT_CONSTRAINT,
            cls.ORDER_CANDIDATE,
            cls.BACKTEST,
            cls.AUDIT,
        }


class FeedbackTargetLayer:
    MACRO = "MACRO"
    SECTOR_ASSET = "SECTOR_ASSET"
    RISK_BUDGET = "RISK_BUDGET"
    ALLOCATION = "ALLOCATION"
    REBALANCING = "REBALANCING"
    ORDER_CANDIDATE = "ORDER_CANDIDATE"
    PARAMETER_REGISTRY = "PARAMETER_REGISTRY"
    AUDIT = "AUDIT"

    @classmethod
    def values(cls) -> set[str]:
        return {
            cls.MACRO,
            cls.SECTOR_ASSET,
            cls.RISK_BUDGET,
            cls.ALLOCATION,
            cls.REBALANCING,
            cls.ORDER_CANDIDATE,
            cls.PARAMETER_REGISTRY,
            cls.AUDIT,
        }


CONSERVATIVE_RECOMMENDED_ACTIONS = frozenset(
    {"NO_ACTION", "HOLD", "REVIEW_REQUIRED", "RISK_REDUCE_ONLY", "REDUCE_ONLY", "BLOCK"}
)
FORBIDDEN_RECOMMENDED_ACTIONS = frozenset(
    {"AUTO_EXECUTE", "SUBMIT_ORDER", "BROKER_MUTATION", "INCREASE_RISK"}
)


@dataclass(frozen=True)
class FeedbackSignal:
    signal_id: str
    source_layer: str
    target_layers: tuple[str, ...]
    severity: str
    timing: str
    as_of_date: date
    reason_codes: tuple[str, ...]
    message: str
    subject_id: str | None = None
    subject_type: str | None = None
    recommended_action: str | None = None
    limits: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.signal_id, "signal_id")
        _require_text(self.source_layer, "source_layer")
        _require_text(self.severity, "severity")
        _require_text(self.timing, "timing")
        _require_text(self.message, "message")
        if self.as_of_date is None:
            raise FeedbackContractError("as_of_date is required")
        if self.source_layer not in FeedbackSourceLayer.values():
            raise FeedbackContractError("source_layer is not allowed")
        if self.severity not in FeedbackSeverity.values():
            raise FeedbackContractError("severity is not allowed")
        if self.timing not in FeedbackTiming.values():
            raise FeedbackContractError("timing is not allowed")
        if not self.target_layers and self.timing != FeedbackTiming.AUDIT_ONLY:
            raise FeedbackContractError("target_layers is required unless timing is AUDIT_ONLY")
        invalid_targets = [target for target in self.target_layers if target not in FeedbackTargetLayer.values()]
        if invalid_targets:
            raise FeedbackContractError("target_layers contains an unsupported layer")
        for reason in self.reason_codes:
            _require_text(reason, "reason_code")
        if self.recommended_action is not None:
            _validate_recommended_action(self.recommended_action)


def review_required_signal(
    *,
    signal_id: str,
    source_layer: str,
    target_layers: tuple[str, ...],
    as_of_date: date,
    reason_codes: tuple[str, ...],
    message: str,
    subject_id: str | None = None,
    subject_type: str | None = None,
) -> FeedbackSignal:
    return FeedbackSignal(
        signal_id=signal_id,
        source_layer=source_layer,
        target_layers=target_layers,
        severity=FeedbackSeverity.REVIEW_REQUIRED,
        timing=FeedbackTiming.SAME_RUN_REFINEMENT,
        as_of_date=as_of_date,
        reason_codes=reason_codes,
        message=message,
        subject_id=subject_id,
        subject_type=subject_type,
        recommended_action="REVIEW_REQUIRED",
    )


def risk_reduce_only_signal(
    *,
    signal_id: str,
    source_layer: str,
    target_layers: tuple[str, ...],
    as_of_date: date,
    reason_codes: tuple[str, ...],
    message: str,
    subject_id: str | None = None,
    subject_type: str | None = None,
) -> FeedbackSignal:
    return FeedbackSignal(
        signal_id=signal_id,
        source_layer=source_layer,
        target_layers=target_layers,
        severity=FeedbackSeverity.REDUCE_ONLY,
        timing=FeedbackTiming.SAME_RUN_REFINEMENT,
        as_of_date=as_of_date,
        reason_codes=reason_codes,
        message=message,
        subject_id=subject_id,
        subject_type=subject_type,
        recommended_action="RISK_REDUCE_ONLY",
    )


def block_signal(
    *,
    signal_id: str,
    source_layer: str,
    target_layers: tuple[str, ...],
    as_of_date: date,
    reason_codes: tuple[str, ...],
    message: str,
    subject_id: str | None = None,
    subject_type: str | None = None,
) -> FeedbackSignal:
    return FeedbackSignal(
        signal_id=signal_id,
        source_layer=source_layer,
        target_layers=target_layers,
        severity=FeedbackSeverity.BLOCK,
        timing=FeedbackTiming.SAME_RUN_REFINEMENT,
        as_of_date=as_of_date,
        reason_codes=reason_codes,
        message=message,
        subject_id=subject_id,
        subject_type=subject_type,
        recommended_action="REVIEW_REQUIRED",
    )


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise FeedbackContractError(f"{field_name} must be a non-empty string")


def _validate_recommended_action(value: str) -> None:
    _require_text(value, "recommended_action")
    if value in FORBIDDEN_RECOMMENDED_ACTIONS:
        raise FeedbackContractError("recommended_action cannot imply live execution or risk increase")
    if value not in CONSERVATIVE_RECOMMENDED_ACTIONS:
        raise FeedbackContractError("recommended_action must be conservative or review-only")
