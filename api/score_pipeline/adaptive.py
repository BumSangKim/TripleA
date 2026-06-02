from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Mapping

from api.score_pipeline.contracts import ConservativeAction, PipelineContractError, clamp_ratio


class AdaptiveNormalizationMethod(str, Enum):
    ROLLING_Z_SCORE = "rolling_z_score"
    ROLLING_PERCENTILE = "rolling_percentile"
    ROBUST_PERCENTILE = "robust_percentile"


RISK_INCREASING_ACTION_TERMS = frozenset(
    {
        "BUY",
        "INCREASE_RISK",
        "INCREASE_SATELLITE_WEIGHT",
        "FORCE_REBALANCE",
        "AUTO_EXECUTE",
        "LIVE_EXECUTE",
        "PLACE_ORDER",
        "SUBMIT_ORDER",
    }
)


@dataclass(frozen=True)
class AdaptiveNormalizationConfig:
    method: AdaptiveNormalizationMethod
    lookback_periods: int
    lookback_months: int
    min_observations: int
    parameter_version: str
    model_version: str
    reason_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.method, AdaptiveNormalizationMethod):
            raise PipelineContractError("method must be an AdaptiveNormalizationMethod")
        _require_positive_int(self.lookback_periods, "lookback_periods")
        _require_positive_int(self.lookback_months, "lookback_months")
        _require_positive_int(self.min_observations, "min_observations")
        _require_text(self.parameter_version, "parameter_version")
        _require_text(self.model_version, "model_version")
        _require_text_tuple(self.reason_codes, "reason_codes")
        _require_text_tuple(self.warnings, "warnings")


@dataclass(frozen=True)
class AdaptiveCalibrationWindow:
    fit_start_date: date
    fit_end_date: date
    decision_date: date
    observation_count: int
    available_at_cutoff: datetime
    parameter_version: str
    model_version: str
    reason_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.fit_start_date is None:
            raise PipelineContractError("fit_start_date is required")
        if self.fit_end_date is None:
            raise PipelineContractError("fit_end_date is required")
        if self.decision_date is None:
            raise PipelineContractError("decision_date is required")
        if self.available_at_cutoff is None:
            raise PipelineContractError("available_at_cutoff is required")
        if self.fit_start_date > self.fit_end_date:
            raise PipelineContractError("fit_start_date cannot be after fit_end_date")
        if self.fit_end_date > self.decision_date:
            raise PipelineContractError("fit window cannot extend beyond decision_date")
        if self.available_at_cutoff.date() > self.decision_date:
            raise PipelineContractError("available_at_cutoff cannot be after decision_date")
        if self.observation_count < 0:
            raise PipelineContractError("observation_count cannot be negative")
        _require_text(self.parameter_version, "parameter_version")
        _require_text(self.model_version, "model_version")
        _require_text_tuple(self.reason_codes, "reason_codes")
        _require_text_tuple(self.warnings, "warnings")

    def has_sufficient_observations(self, config: AdaptiveNormalizationConfig) -> bool:
        return self.observation_count >= config.min_observations


@dataclass(frozen=True)
class AdaptiveCalibrationReport:
    method: AdaptiveNormalizationMethod
    fit_start_date: date
    fit_end_date: date
    decision_date: date
    observation_count: int
    min_observations: int
    available_at_cutoff: datetime
    parameter_version: str
    model_version: str
    is_usable: bool
    fallback_state: str | None = None
    reason_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.method, AdaptiveNormalizationMethod):
            raise PipelineContractError("method must be an AdaptiveNormalizationMethod")
        if self.fit_start_date is None or self.fit_end_date is None or self.decision_date is None:
            raise PipelineContractError("fit and decision dates are required")
        if self.fit_start_date > self.fit_end_date:
            raise PipelineContractError("fit_start_date cannot be after fit_end_date")
        if self.fit_end_date > self.decision_date:
            raise PipelineContractError("fit window cannot extend beyond decision_date")
        if self.available_at_cutoff is None:
            raise PipelineContractError("available_at_cutoff is required")
        if self.available_at_cutoff.date() > self.decision_date:
            raise PipelineContractError("available_at_cutoff cannot be after decision_date")
        if self.observation_count < 0:
            raise PipelineContractError("observation_count cannot be negative")
        _require_positive_int(self.min_observations, "min_observations")
        _require_text(self.parameter_version, "parameter_version")
        _require_text(self.model_version, "model_version")
        if self.observation_count < self.min_observations and self.fallback_state not in ConservativeAction.values():
            raise PipelineContractError("insufficient observations require conservative fallback_state")
        if self.is_usable and self.observation_count < self.min_observations:
            raise PipelineContractError("insufficient observations cannot be usable")
        _require_text_tuple(self.reason_codes, "reason_codes")
        _require_text_tuple(self.warnings, "warnings")

    @classmethod
    def from_window(
        cls,
        config: AdaptiveNormalizationConfig,
        window: AdaptiveCalibrationWindow,
    ) -> AdaptiveCalibrationReport:
        sufficient = window.has_sufficient_observations(config)
        reason_codes = [*config.reason_codes, *window.reason_codes]
        warnings = [*config.warnings, *window.warnings]
        fallback_state = None
        if not sufficient:
            fallback_state = ConservativeAction.REVIEW_REQUIRED
            reason_codes.append("INSUFFICIENT_ADAPTIVE_CALIBRATION_OBSERVATIONS")
            warnings.append("adaptive calibration has insufficient observations")
        return cls(
            method=config.method,
            fit_start_date=window.fit_start_date,
            fit_end_date=window.fit_end_date,
            decision_date=window.decision_date,
            observation_count=window.observation_count,
            min_observations=config.min_observations,
            available_at_cutoff=window.available_at_cutoff,
            parameter_version=config.parameter_version,
            model_version=config.model_version,
            is_usable=sufficient,
            fallback_state=fallback_state,
            reason_codes=tuple(reason_codes),
            warnings=tuple(warnings),
        )


@dataclass(frozen=True)
class AdaptiveNormalizedValue:
    raw_value: float | None
    normalized_value: float
    method: AdaptiveNormalizationMethod
    calibration_report: AdaptiveCalibrationReport
    confidence: float
    data_quality: float
    parameter_version: str
    model_version: str
    fallback_state: str | None = None
    reason_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_ratio(self.normalized_value, "normalized_value")
        if not isinstance(self.method, AdaptiveNormalizationMethod):
            raise PipelineContractError("method must be an AdaptiveNormalizationMethod")
        _require_ratio(self.confidence, "confidence")
        _require_ratio(self.data_quality, "data_quality")
        _require_text(self.parameter_version, "parameter_version")
        _require_text(self.model_version, "model_version")
        if self.method != self.calibration_report.method:
            raise PipelineContractError("method must match calibration_report")
        if not self.calibration_report.is_usable and self.fallback_state not in ConservativeAction.values():
            raise PipelineContractError("unusable calibration requires conservative fallback_state")
        _require_text_tuple(self.reason_codes, "reason_codes")
        _require_text_tuple(self.warnings, "warnings")


@dataclass(frozen=True)
class StaticValueAuditResult:
    subject: str
    static_values_found: tuple[str, ...] = ()
    action_mapping_terms: tuple[str, ...] = ()
    is_blocking: bool = False
    reason_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.subject, "subject")
        _require_text_tuple(self.static_values_found, "static_values_found")
        _require_text_tuple(self.action_mapping_terms, "action_mapping_terms")
        _require_text_tuple(self.reason_codes, "reason_codes")
        _require_text_tuple(self.warnings, "warnings")
        if self.action_mapping_terms and not self.is_blocking:
            raise PipelineContractError("action mapping terms must be blocking")

    @classmethod
    def audit_mapping(cls, subject: str, mapping: Mapping[str, Any]) -> StaticValueAuditResult:
        if not isinstance(mapping, Mapping):
            raise PipelineContractError("mapping must be a mapping")
        static_values: list[str] = []
        action_terms: list[str] = []
        _scan_static_mapping(mapping, prefix="", static_values=static_values, action_terms=action_terms)
        reason_codes = ("STATIC_VALUE_AUDIT_BLOCKED",) if action_terms else ()
        warnings = ("hardcoded action mapping terms found",) if action_terms else ()
        return cls(
            subject=subject,
            static_values_found=tuple(sorted(set(static_values))),
            action_mapping_terms=tuple(sorted(set(action_terms))),
            is_blocking=bool(action_terms),
            reason_codes=reason_codes,
            warnings=warnings,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def to_serializable_dict(value: Any) -> dict[str, Any]:
    return asdict(value)


def _scan_static_mapping(
    mapping: Mapping[str, Any],
    *,
    prefix: str,
    static_values: list[str],
    action_terms: list[str],
) -> None:
    for key, value in mapping.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        upper_key = str(key).upper()
        if upper_key in RISK_INCREASING_ACTION_TERMS:
            action_terms.append(path)
        if isinstance(value, Mapping):
            _scan_static_mapping(value, prefix=path, static_values=static_values, action_terms=action_terms)
            continue
        if isinstance(value, str) and value.upper() in RISK_INCREASING_ACTION_TERMS:
            action_terms.append(path)
        if isinstance(value, int | float | str | bool):
            static_values.append(path)


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PipelineContractError(f"{field_name} must be a non-empty string")


def _require_text_tuple(value: tuple[str, ...], field_name: str) -> None:
    if not isinstance(value, tuple):
        raise PipelineContractError(f"{field_name} must be a tuple")
    for item in value:
        _require_text(item, field_name)


def _require_positive_int(value: int, field_name: str) -> None:
    if not isinstance(value, int) or value <= 0:
        raise PipelineContractError(f"{field_name} must be a positive integer")


def _require_ratio(value: float, field_name: str) -> None:
    try:
        clamp_ratio(value)
    except (TypeError, ValueError) as exc:
        raise PipelineContractError(f"{field_name} must be between 0 and 1") from exc
    if not 0.0 <= float(value) <= 1.0:
        raise PipelineContractError(f"{field_name} must be between 0 and 1")
