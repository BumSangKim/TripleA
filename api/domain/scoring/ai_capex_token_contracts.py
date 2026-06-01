from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Mapping


class AICapexTokenContractError(ValueError):
    pass


class TokenConsumptionDirection(str, Enum):
    EXPANDING = "expanding"
    STABLE = "stable"
    CONTRACTING = "contracting"


class CapexAccelerationDirection(str, Enum):
    ACCELERATING = "accelerating"
    STABLE = "stable"
    DECELERATING = "decelerating"


class AICapexTokenScenario(str, Enum):
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"
    S4 = "S4"
    S5 = "S5"
    S6 = "S6"
    S7 = "S7"
    S8 = "S8"
    S9 = "S9"


class AICapexTokenFallbackState(str, Enum):
    NO_ACTION = "NO_ACTION"
    HOLD = "HOLD"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    RISK_REDUCE_ONLY = "RISK_REDUCE_ONLY"
    DIAGNOSTIC_ONLY = "diagnostic_only"


TOKEN_PERIOD_ROLES = frozenset({"current", "previous"})
CAPEX_PERIOD_ROLES = frozenset({"t", "t_minus_1", "t_minus_2"})
TOKEN_CURRENT_PERIOD_ROLE = "current"
TOKEN_PREVIOUS_PERIOD_ROLE = "previous"
CAPEX_CURRENT_PERIOD_ROLE = "t"
CAPEX_PREVIOUS_PERIOD_ROLE = "t_minus_1"
CAPEX_PRIOR_PREVIOUS_PERIOD_ROLE = "t_minus_2"
RISK_INCREASING_FALLBACKS = frozenset(
    {"BUY", "INCREASE_RISK", "INCREASE_SATELLITE_WEIGHT", "FORCE_REBALANCE", "AUTO_EXECUTE"}
)


@dataclass(frozen=True)
class AICapexTokenMetric:
    metric_key: str
    period_role: str
    value: float
    as_of_date: date
    available_at: datetime
    source: str
    quality_score: float
    missing_ratio: float = 0.0
    is_stale: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.metric_key, "metric_key")
        _require_text(self.period_role, "period_role")
        _require_text(self.source, "source")
        _require_ratio(self.quality_score, "quality_score")
        _require_ratio(self.missing_ratio, "missing_ratio")
        if self.as_of_date is None:
            raise AICapexTokenContractError("as_of_date is required")
        if self.available_at is None:
            raise AICapexTokenContractError("available_at is required")
        if not isinstance(self.metadata, Mapping):
            raise AICapexTokenContractError("metadata must be a mapping")
        if self.period_role not in TOKEN_PERIOD_ROLES | CAPEX_PERIOD_ROLES:
            raise AICapexTokenContractError("period_role is not allowed")


@dataclass(frozen=True)
class AICapexTokenRawSnapshot:
    snapshot_id: str
    decision_date: date
    token_sources_current: tuple[AICapexTokenMetric, ...]
    token_sources_previous: tuple[AICapexTokenMetric, ...]
    capex_series: tuple[AICapexTokenMetric, ...]
    sector_metrics: Mapping[str, Mapping[str, float]]
    macro_overlay_metrics: Mapping[str, float] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.snapshot_id, "snapshot_id")
        if self.decision_date is None:
            raise AICapexTokenContractError("decision_date is required")
        _require_metric_tuple(self.token_sources_current, "token_sources_current")
        _require_metric_tuple(self.token_sources_previous, "token_sources_previous")
        _require_metric_tuple(self.capex_series, "capex_series")
        for metric in self.token_sources_current:
            validate_token_period_role(metric.period_role, expected=TOKEN_CURRENT_PERIOD_ROLE)
        for metric in self.token_sources_previous:
            validate_token_period_role(metric.period_role, expected=TOKEN_PREVIOUS_PERIOD_ROLE)
        capex_roles = {metric.period_role for metric in self.capex_series}
        missing_roles = CAPEX_PERIOD_ROLES - capex_roles
        if missing_roles:
            raise AICapexTokenContractError(f"capex_series missing period roles: {sorted(missing_roles)}")
        for metric in self.capex_series:
            validate_capex_period_role(metric.period_role)
        if not isinstance(self.sector_metrics, Mapping):
            raise AICapexTokenContractError("sector_metrics must be a mapping")
        if not isinstance(self.macro_overlay_metrics, Mapping):
            raise AICapexTokenContractError("macro_overlay_metrics must be a mapping")


@dataclass(frozen=True)
class AICapexTokenFeatureSet:
    snapshot_id: str
    as_of_date: date
    token_consumption_change: float | None
    capex_growth: float | None
    capex_acceleration: float | None
    token_direction: TokenConsumptionDirection
    capex_direction: CapexAccelerationDirection
    data_quality: float
    fallback_state: AICapexTokenFallbackState | None = None
    reason_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.snapshot_id, "snapshot_id")
        if self.as_of_date is None:
            raise AICapexTokenContractError("as_of_date is required")
        _require_ratio(self.data_quality, "data_quality")
        _require_tuple_text(self.reason_codes, "reason_codes")
        _require_tuple_text(self.warnings, "warnings")
        if self.fallback_state is not None:
            validate_fallback_state(self.fallback_state.value)


@dataclass(frozen=True)
class AICapexTokenScenarioDistribution:
    as_of_date: date
    probabilities: Mapping[str, float]
    dominant_scenario: str
    dominant_scenario_explanation_only: bool
    data_quality: float
    confidence: float
    fallback_state: AICapexTokenFallbackState | None = None
    reason_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.as_of_date is None:
            raise AICapexTokenContractError("as_of_date is required")
        validate_scenario_distribution(self.probabilities)
        if self.dominant_scenario not in scenario_ids():
            raise AICapexTokenContractError("dominant_scenario is not allowed")
        if self.dominant_scenario_explanation_only is not True:
            raise AICapexTokenContractError("dominant_scenario must be explanation-only")
        _require_ratio(self.data_quality, "data_quality")
        _require_ratio(self.confidence, "confidence")
        if self.fallback_state is not None:
            validate_fallback_state(self.fallback_state.value)


@dataclass(frozen=True)
class AICapexTokenSectorComponentScore:
    sector_id: str
    as_of_date: date
    component_score: float
    confidence: float
    data_quality: float
    diagnostic_only: bool
    scenario_distribution: AICapexTokenScenarioDistribution
    fallback_state: AICapexTokenFallbackState | None = None
    reason_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    parameter_version: str = "unapproved"
    model_version: str = "ai_capex_token_contract_v1"

    def __post_init__(self) -> None:
        _require_text(self.sector_id, "sector_id")
        if self.as_of_date is None:
            raise AICapexTokenContractError("as_of_date is required")
        for field_name in ("component_score", "confidence", "data_quality"):
            _require_ratio(getattr(self, field_name), field_name)
        if self.diagnostic_only is not True:
            raise AICapexTokenContractError("sector component must be diagnostic_only until approved")
        if self.fallback_state is not None:
            validate_fallback_state(self.fallback_state.value)
        _require_tuple_text(self.reason_codes, "reason_codes")
        _require_tuple_text(self.warnings, "warnings")
        _require_text(self.parameter_version, "parameter_version")
        _require_text(self.model_version, "model_version")

    def to_score_signal_dict(self) -> dict[str, Any]:
        previous_score = None
        return {
            "score": self.component_score,
            "previous_score": previous_score,
            "score_change": None,
            "confidence": self.confidence,
            "data_quality": self.data_quality,
            "stability": 1.0,
            "adjustment_intensity": 0.0,
            "reason_codes": list(self.reason_codes),
            "as_of_date": self.as_of_date,
            "parameter_version": self.parameter_version,
            "model_version": self.model_version,
            "components": [
                {
                    "name": "ai_capex_token",
                    "value": self.component_score,
                    "weight": 1.0,
                    "contribution": self.component_score,
                    "reason_codes": list(self.reason_codes),
                }
            ],
        }


def validate_token_period_role(period_role: str, *, expected: str | None = None) -> str:
    _require_text(period_role, "period_role")
    if period_role not in TOKEN_PERIOD_ROLES:
        raise AICapexTokenContractError("token period_role must be current or previous")
    if expected is not None and period_role != expected:
        raise AICapexTokenContractError(f"token period_role must be {expected}")
    return period_role


def validate_capex_period_role(period_role: str, *, expected: str | None = None) -> str:
    _require_text(period_role, "period_role")
    if period_role not in CAPEX_PERIOD_ROLES:
        raise AICapexTokenContractError("capex period_role must be t, t_minus_1, or t_minus_2")
    if expected is not None and period_role != expected:
        raise AICapexTokenContractError(f"capex period_role must be {expected}")
    return period_role


def validate_scenario_distribution(probabilities: Mapping[str, float]) -> Mapping[str, float]:
    if not isinstance(probabilities, Mapping):
        raise AICapexTokenContractError("probabilities must be a mapping")
    expected = scenario_ids()
    actual = set(probabilities)
    if actual != expected:
        raise AICapexTokenContractError("probabilities must contain exactly S1 through S9")
    total = 0.0
    for scenario_id, probability in probabilities.items():
        _require_ratio(probability, scenario_id)
        total += float(probability)
    if abs(total - 1.0) > 1e-6:
        raise AICapexTokenContractError("scenario probabilities must sum to 1.0")
    return probabilities


def validate_fallback_state(value: str) -> str:
    _require_text(value, "fallback_state")
    if value in RISK_INCREASING_FALLBACKS:
        raise AICapexTokenContractError("fallback_state must not increase risk")
    allowed = {item.value for item in AICapexTokenFallbackState}
    if value not in allowed:
        raise AICapexTokenContractError("fallback_state is not allowed")
    return value


def scenario_ids() -> set[str]:
    return {scenario.value for scenario in AICapexTokenScenario}


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise AICapexTokenContractError(f"{field_name} must be a non-empty string")


def _require_ratio(value: float, field_name: str) -> None:
    if value is None or not 0.0 <= float(value) <= 1.0:
        raise AICapexTokenContractError(f"{field_name} must be between 0 and 1")


def _require_tuple_text(value: tuple[str, ...], field_name: str) -> None:
    if not isinstance(value, tuple):
        raise AICapexTokenContractError(f"{field_name} must be a tuple")
    for item in value:
        _require_text(item, field_name)


def _require_metric_tuple(value: tuple[AICapexTokenMetric, ...], field_name: str) -> None:
    if not isinstance(value, tuple):
        raise AICapexTokenContractError(f"{field_name} must be a tuple")
    for item in value:
        if not isinstance(item, AICapexTokenMetric):
            raise AICapexTokenContractError(f"{field_name} must contain AICapexTokenMetric values")
