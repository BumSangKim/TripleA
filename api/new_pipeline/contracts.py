from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any


class PipelineContractError(ValueError):
    pass


class ConservativeAction:
    NO_ACTION = "NO_ACTION"
    HOLD = "HOLD"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    RISK_REDUCE_ONLY = "RISK_REDUCE_ONLY"

    @classmethod
    def values(cls) -> set[str]:
        return {cls.NO_ACTION, cls.HOLD, cls.REVIEW_REQUIRED, cls.RISK_REDUCE_ONLY}


class CandidateAction:
    BUY = "BUY"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    SELL = "SELL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"

    @classmethod
    def values(cls) -> set[str]:
        return {cls.BUY, cls.HOLD, cls.REDUCE, cls.SELL, cls.REVIEW_REQUIRED, cls.BLOCKED}


@dataclass(frozen=True)
class ReasonCode:
    code: str
    category: str
    detail: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.code, "code")
        _require_text(self.category, "category")


@dataclass(frozen=True)
class DecisionWarning:
    code: str
    severity: str
    source: str
    message: str

    def __post_init__(self) -> None:
        _require_text(self.code, "code")
        if self.severity not in {"INFO", "WARNING", "ERROR", "BLOCKER"}:
            raise PipelineContractError("severity must be INFO, WARNING, ERROR, or BLOCKER")
        _require_text(self.source, "source")
        _require_text(self.message, "message")


@dataclass(frozen=True)
class ParameterVersionRef:
    version: str
    source: str

    def __post_init__(self) -> None:
        _require_text(self.version, "version")
        _require_text(self.source, "source")


@dataclass(frozen=True)
class ModelVersionRef:
    version: str
    name: str

    def __post_init__(self) -> None:
        _require_text(self.version, "version")
        _require_text(self.name, "name")


@dataclass(frozen=True)
class DataQualityMetadata:
    source: str
    as_of_date: date
    updated_at: datetime
    quality_score: float
    missing_ratio: float
    is_stale: bool = False
    warnings: list[DecisionWarning] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_text(self.source, "source")
        if self.as_of_date is None:
            raise PipelineContractError("as_of_date is required")
        if self.updated_at is None:
            raise PipelineContractError("updated_at is required")
        _require_ratio(self.quality_score, "quality_score")
        _require_ratio(self.missing_ratio, "missing_ratio")

    @property
    def conservative_action(self) -> str | None:
        if self.missing_ratio >= 1.0 or self.quality_score < 0.4:
            return ConservativeAction.REVIEW_REQUIRED
        if self.is_stale or self.quality_score < 0.7:
            return ConservativeAction.HOLD
        return None


@dataclass(frozen=True)
class FeatureOutput:
    feature_id: str
    feature_name: str
    entity_id: str
    entity_type: str
    raw_value: float | None
    normalized_value: float
    confidence: float
    data_quality: DataQualityMetadata
    as_of_date: date
    source: str
    parameter_version: str
    model_version: str
    reason_codes: list[ReasonCode] = field(default_factory=list)
    warnings: list[DecisionWarning] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in ("feature_id", "feature_name", "entity_id", "entity_type", "source", "parameter_version", "model_version"):
            _require_text(getattr(self, field_name), field_name)
        _require_ratio(self.normalized_value, "normalized_value")
        _require_ratio(self.confidence, "confidence")


@dataclass(frozen=True)
class ScoreOutput:
    score_id: str
    subject_id: str
    subject_type: str
    score: float
    previous_score: float | None
    score_change: float
    confidence: float
    data_quality: float
    stability: float
    adjustment_intensity: float
    as_of_date: date
    parameter_version: str
    model_version: str
    reason_codes: list[ReasonCode] = field(default_factory=list)
    warnings: list[DecisionWarning] = field(default_factory=list)
    normalized_score: float | None = None
    smoothed_score: float | None = None
    confidence_adjusted_score: float | None = None
    data_quality_adjusted_score: float | None = None

    def __post_init__(self) -> None:
        for field_name in ("score_id", "subject_id", "subject_type", "parameter_version", "model_version"):
            _require_text(getattr(self, field_name), field_name)
        for field_name in ("score", "confidence", "data_quality", "stability", "adjustment_intensity"):
            _require_ratio(getattr(self, field_name), field_name)
        for optional in ("normalized_score", "smoothed_score", "confidence_adjusted_score", "data_quality_adjusted_score"):
            value = getattr(self, optional)
            if value is not None:
                _require_ratio(value, optional)


@dataclass(frozen=True)
class MacroRegimeDistribution:
    as_of_date: date
    distribution: dict[str, float]
    dominant_regime: str
    dominant_regime_explanation_only: bool
    confidence: float
    data_quality: float
    reason_codes: list[ReasonCode]
    warnings: list[DecisionWarning]
    parameter_version: str
    model_version: str

    def __post_init__(self) -> None:
        if not self.distribution:
            raise PipelineContractError("distribution is required")
        for value in self.distribution.values():
            _require_ratio(value, "distribution value")
        _require_ratio(self.confidence, "confidence")
        _require_ratio(self.data_quality, "data_quality")
        _require_text(self.dominant_regime, "dominant_regime")


@dataclass(frozen=True)
class SectorScoreOutput:
    sector_id: str
    total_score: float
    component_scores: dict[str, float]
    score: float
    previous_score: float | None
    score_change: float
    confidence: float
    data_quality: float
    stability: float
    adjustment_intensity: float
    as_of_date: date
    parameter_version: str
    model_version: str
    reason_codes: list[ReasonCode] = field(default_factory=list)
    warnings: list[DecisionWarning] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_text(self.sector_id, "sector_id")
        for field_name in ("total_score", "score", "confidence", "data_quality", "stability", "adjustment_intensity"):
            _require_ratio(getattr(self, field_name), field_name)
        for value in self.component_scores.values():
            _require_ratio(value, "component score")


@dataclass(frozen=True)
class ConstraintResult:
    passed: bool
    blocked: bool
    reason_codes: list[ReasonCode] = field(default_factory=list)
    warnings: list[DecisionWarning] = field(default_factory=list)
    conservative_action: str | None = None

    def __post_init__(self) -> None:
        if self.conservative_action is not None and self.conservative_action not in ConservativeAction.values():
            raise PipelineContractError("invalid conservative_action")
        if self.blocked and self.passed:
            raise PipelineContractError("constraint cannot be both passed and blocked")


@dataclass(frozen=True)
class RiskBudgetOutput:
    portfolio_risk_score: float
    account_risk_score: float
    risk_penalty: float
    risk_capacity: float
    constraint_result: ConstraintResult
    score: float
    previous_score: float | None
    score_change: float
    confidence: float
    data_quality: float
    stability: float
    adjustment_intensity: float
    as_of_date: date
    parameter_version: str
    model_version: str
    reason_codes: list[ReasonCode] = field(default_factory=list)
    warnings: list[DecisionWarning] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in ("portfolio_risk_score", "account_risk_score", "risk_penalty", "risk_capacity", "score", "confidence", "data_quality", "stability", "adjustment_intensity"):
            _require_ratio(getattr(self, field_name), field_name)


@dataclass(frozen=True)
class AllocationTargetRange:
    asset_id: str
    min_weight: float
    base_weight: float
    max_weight: float
    current_target: float
    previous_target: float
    confidence: float
    data_quality: float
    as_of_date: date
    parameter_version: str
    model_version: str
    reason_codes: list[ReasonCode] = field(default_factory=list)
    warnings: list[DecisionWarning] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_text(self.asset_id, "asset_id")
        for field_name in ("min_weight", "base_weight", "max_weight", "current_target", "previous_target", "confidence", "data_quality"):
            _require_ratio(getattr(self, field_name), field_name)
        if not self.min_weight <= self.base_weight <= self.max_weight:
            raise PipelineContractError("target range must satisfy min <= base <= max")
        if not self.min_weight <= self.current_target <= self.max_weight:
            raise PipelineContractError("current_target must be within range")


@dataclass(frozen=True)
class RebalancingDecision:
    asset_id: str
    action: str
    intensity: float
    target_weight: float
    current_weight: float
    score: float
    previous_score: float | None
    score_change: float
    confidence: float
    data_quality: float
    stability: float
    adjustment_intensity: float
    as_of_date: date
    parameter_version: str
    model_version: str
    reason_codes: list[ReasonCode] = field(default_factory=list)
    warnings: list[DecisionWarning] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.action not in CandidateAction.values() | ConservativeAction.values() | {"LIMITED_INCREASE", "STOP_NEW_BUYS"}:
            raise PipelineContractError("unsupported rebalancing action")
        for field_name in ("intensity", "target_weight", "current_weight", "score", "confidence", "data_quality", "stability", "adjustment_intensity"):
            _require_ratio(getattr(self, field_name), field_name)


@dataclass(frozen=True)
class OrderCandidate:
    candidate_id: str
    account_id: str
    asset_id: str
    action_candidate: str
    target_weight: float
    current_weight: float
    target_quantity_estimate: float | None
    estimated_amount: float
    cash_impact: float
    constraint_result: ConstraintResult
    reason_codes: list[ReasonCode]
    warnings: list[DecisionWarning]
    requires_user_review: bool
    execution_allowed: bool
    as_of_date: date
    parameter_version: str
    model_version: str

    def __post_init__(self) -> None:
        for field_name in ("candidate_id", "account_id", "asset_id", "parameter_version", "model_version"):
            _require_text(getattr(self, field_name), field_name)
        if self.action_candidate not in CandidateAction.values():
            raise PipelineContractError("unsupported action_candidate")
        if self.execution_allowed is not False:
            raise PipelineContractError("execution_allowed must default to false in new pipeline")
        for field_name in ("target_weight", "current_weight"):
            _require_ratio(getattr(self, field_name), field_name)


@dataclass(frozen=True)
class DecisionLogRecord:
    date: date
    data_snapshot_id: str
    parameter_version: str
    model_version: str
    macro_scores: dict[str, Any]
    sector_scores: dict[str, Any]
    risk_budget_scores: dict[str, Any]
    target_weights: dict[str, float]
    current_weights: dict[str, float]
    rebalance_scores: dict[str, Any]
    account_constraints: dict[str, Any]
    decision: str
    adjustment_intensity: float
    reason_codes: list[ReasonCode]
    warnings: list[DecisionWarning]

    def __post_init__(self) -> None:
        for field_name in ("data_snapshot_id", "parameter_version", "model_version", "decision"):
            _require_text(getattr(self, field_name), field_name)
        _require_ratio(self.adjustment_intensity, "adjustment_intensity")


def to_serializable_dict(value: Any) -> dict[str, Any]:
    return asdict(value)


def to_json(value: Any) -> str:
    return json.dumps(to_serializable_dict(value), default=str, sort_keys=True)


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PipelineContractError(f"{field_name} must be a non-empty string")


def _require_ratio(value: float, field_name: str) -> None:
    if value is None or not 0.0 <= float(value) <= 1.0:
        raise PipelineContractError(f"{field_name} must be between 0 and 1")


def clamp_ratio(value: float) -> float:
    return max(0.0, min(1.0, float(value)))

