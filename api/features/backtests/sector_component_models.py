from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime
from typing import Any


CONSERVATIVE_FALLBACK_STATES = {"NO_ACTION", "HOLD", "REVIEW_REQUIRED", "RISK_REDUCE_ONLY"}


@dataclass(frozen=True)
class SectorComponentValidationWarning:
    sector_id: str
    as_of_date: date
    available_at: datetime
    parameter_version: str
    model_version: str
    data_snapshot_id: str
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    code: str = "REVIEW_REQUIRED"
    message: str = "review required"
    component_name: str | None = None
    severity: str = "WARNING"
    fallback_state: str = "REVIEW_REQUIRED"

    def __post_init__(self) -> None:
        if self.fallback_state not in CONSERVATIVE_FALLBACK_STATES:
            raise ValueError("fallback_state must be conservative")
        _coerce_tuple(self, "reason_codes")
        _coerce_tuple(self, "warnings")

    def to_dict(self) -> dict[str, Any]:
        return _serialize_dataclass(self)


@dataclass(frozen=True)
class SectorComponentObservation:
    sector_id: str
    component_name: str
    score: float | None
    as_of_date: date
    available_at: datetime
    parameter_version: str
    model_version: str
    data_snapshot_id: str
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[SectorComponentValidationWarning, ...] = field(default_factory=tuple)
    confidence: float = 1.0
    data_quality: float = 1.0
    source: str | None = None

    def __post_init__(self) -> None:
        _coerce_tuple(self, "reason_codes")
        _coerce_tuple(self, "warnings")
        warnings = list(self.warnings)
        if self.score is None:
            warnings.append(self.review_warning("COMPONENT_SCORE_MISSING", "component score is missing"))
        elif not 0.0 <= float(self.score) <= 1.0:
            warnings.append(self.review_warning("COMPONENT_SCORE_OUT_OF_RANGE", f"score={self.score!r}"))
        if not 0.0 <= float(self.confidence) <= 1.0:
            warnings.append(self.review_warning("COMPONENT_CONFIDENCE_OUT_OF_RANGE", f"confidence={self.confidence!r}"))
        if not 0.0 <= float(self.data_quality) <= 1.0:
            warnings.append(self.review_warning("COMPONENT_DATA_QUALITY_OUT_OF_RANGE", f"data_quality={self.data_quality!r}"))
        object.__setattr__(self, "warnings", tuple(warnings))

    @property
    def requires_review(self) -> bool:
        return bool(self.warnings)

    def review_warning(self, code: str, message: str) -> SectorComponentValidationWarning:
        return SectorComponentValidationWarning(
            sector_id=self.sector_id,
            component_name=self.component_name,
            as_of_date=self.as_of_date,
            available_at=self.available_at,
            parameter_version=self.parameter_version,
            model_version=self.model_version,
            data_snapshot_id=self.data_snapshot_id,
            reason_codes=("REVIEW_REQUIRED",),
            warnings=(code,),
            code=code,
            message=message,
        )

    def to_dict(self) -> dict[str, Any]:
        return _serialize_dataclass(self)


@dataclass(frozen=True)
class SectorComponentSnapshot:
    sector_id: str
    as_of_date: date
    available_at: datetime
    parameter_version: str
    model_version: str
    data_snapshot_id: str
    observations: tuple[SectorComponentObservation, ...] = field(default_factory=tuple)
    required_components: tuple[str, ...] = field(default_factory=tuple)
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[SectorComponentValidationWarning, ...] = field(default_factory=tuple)
    fallback_state: str = "HOLD"

    def __post_init__(self) -> None:
        _coerce_tuple(self, "observations")
        _coerce_tuple(self, "required_components")
        _coerce_tuple(self, "reason_codes")
        _coerce_tuple(self, "warnings")
        if self.fallback_state not in CONSERVATIVE_FALLBACK_STATES:
            raise ValueError("fallback_state must be conservative")
        warnings = list(self.warnings)
        present = {observation.component_name for observation in self.observations if observation.score is not None}
        for component_name in sorted(set(self.required_components) - present):
            warnings.append(_tracking_warning(self, "COMPONENT_REQUIRED_INPUT_MISSING", component_name, component_name))
        object.__setattr__(self, "warnings", tuple(warnings))

    @property
    def requires_review(self) -> bool:
        return bool(self.warnings)

    def to_dict(self) -> dict[str, Any]:
        return _serialize_dataclass(self)


@dataclass(frozen=True)
class SectorComponentBacktestRequest:
    sector_id: str
    as_of_date: date
    available_at: datetime
    parameter_version: str
    model_version: str
    data_snapshot_id: str
    start_date: date
    end_date: date
    enabled_components: tuple[str, ...]
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[SectorComponentValidationWarning, ...] = field(default_factory=tuple)
    fallback_state: str = "REVIEW_REQUIRED"

    def __post_init__(self) -> None:
        _coerce_tuple(self, "enabled_components")
        _coerce_tuple(self, "reason_codes")
        _coerce_tuple(self, "warnings")
        if self.fallback_state not in CONSERVATIVE_FALLBACK_STATES:
            raise ValueError("fallback_state must be conservative")
        if self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")

    def to_dict(self) -> dict[str, Any]:
        return _serialize_dataclass(self)


@dataclass(frozen=True)
class SectorComponentMetricSummary:
    sector_id: str
    as_of_date: date
    available_at: datetime
    parameter_version: str
    model_version: str
    data_snapshot_id: str
    total_return: float | None = None
    annualized_return: float | None = None
    max_drawdown: float | None = None
    volatility: float | None = None
    hit_rate: float | None = None
    observation_count: int = 0
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[SectorComponentValidationWarning, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _coerce_tuple(self, "reason_codes")
        _coerce_tuple(self, "warnings")

    def to_dict(self) -> dict[str, Any]:
        return _serialize_dataclass(self)


@dataclass(frozen=True)
class SectorComponentAttributionRow:
    sector_id: str
    component_name: str
    as_of_date: date
    available_at: datetime
    parameter_version: str
    model_version: str
    data_snapshot_id: str
    score: float | None
    weight: float | None
    weighted_contribution: float | None
    contribution_share: float | None
    previous_score: float | None = None
    score_change: float | None = None
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[SectorComponentValidationWarning, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _coerce_tuple(self, "reason_codes")
        _coerce_tuple(self, "warnings")

    def to_dict(self) -> dict[str, Any]:
        return _serialize_dataclass(self)


@dataclass(frozen=True)
class SectorComponentSensitivityResult:
    sector_id: str
    as_of_date: date
    available_at: datetime
    parameter_version: str
    model_version: str
    data_snapshot_id: str
    parameter_set_id: str
    component_weights: dict[str, float]
    metric_summary: SectorComponentMetricSummary
    stability_score: float | None = None
    rank: int | None = None
    approved_for_production: bool = False
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[SectorComponentValidationWarning, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _coerce_tuple(self, "reason_codes")
        _coerce_tuple(self, "warnings")
        if self.approved_for_production:
            raise ValueError("sensitivity results must not auto-approve production parameters")

    def to_dict(self) -> dict[str, Any]:
        return _serialize_dataclass(self)


@dataclass(frozen=True)
class SectorComponentBacktestResult:
    sector_id: str
    as_of_date: date
    available_at: datetime
    parameter_version: str
    model_version: str
    data_snapshot_id: str
    metric_summaries: tuple[SectorComponentMetricSummary, ...] = field(default_factory=tuple)
    attribution_rows: tuple[SectorComponentAttributionRow, ...] = field(default_factory=tuple)
    sensitivity_results: tuple[SectorComponentSensitivityResult, ...] = field(default_factory=tuple)
    regime_breakdowns: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    status: str = "HOLD"
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[SectorComponentValidationWarning, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _coerce_tuple(self, "metric_summaries")
        _coerce_tuple(self, "attribution_rows")
        _coerce_tuple(self, "sensitivity_results")
        _coerce_tuple(self, "regime_breakdowns")
        _coerce_tuple(self, "reason_codes")
        _coerce_tuple(self, "warnings")
        if self.status not in CONSERVATIVE_FALLBACK_STATES | {"OK"}:
            raise ValueError("status must be OK or conservative")

    def to_dict(self) -> dict[str, Any]:
        return _serialize_dataclass(self)


def _tracking_warning(
    item: Any,
    code: str,
    message: str,
    component_name: str | None = None,
) -> SectorComponentValidationWarning:
    return SectorComponentValidationWarning(
        sector_id=item.sector_id,
        component_name=component_name,
        as_of_date=item.as_of_date,
        available_at=item.available_at,
        parameter_version=item.parameter_version,
        model_version=item.model_version,
        data_snapshot_id=item.data_snapshot_id,
        reason_codes=("REVIEW_REQUIRED",),
        warnings=(code,),
        code=code,
        message=message,
    )


def _coerce_tuple(instance: Any, field_name: str) -> None:
    value = getattr(instance, field_name)
    if not isinstance(value, tuple):
        object.__setattr__(instance, field_name, tuple(value or ()))


def _serialize_dataclass(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _serialize_dataclass(item) for key, item in asdict(value).items()}
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_serialize_dataclass(item) for item in value]
    if isinstance(value, list):
        return [_serialize_dataclass(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_dataclass(item) for key, item in value.items()}
    return value

