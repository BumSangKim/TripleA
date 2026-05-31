from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import date
from typing import Any

from api.features.capex_cycle.schemas import ReasonItem, WarningItem


class CapexCycleModelError(ValueError):
    pass


@dataclass(frozen=True)
class CapexScoreSnapshot:
    snapshot_id: str
    score_type: str
    entity_id: str
    score: float
    confidence: float
    data_quality: float
    as_of_date: date
    parameter_version: str
    model_version: str
    reason_codes: list[ReasonItem] = field(default_factory=list)
    warnings: list[WarningItem] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.snapshot_id, "snapshot_id")
        _require_text(self.score_type, "score_type")
        _require_text(self.entity_id, "entity_id")
        _require_versions(self)
        _require_ratio(self.score, "score")
        _require_ratio(self.confidence, "confidence")
        _require_ratio(self.data_quality, "data_quality")

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass(frozen=True)
class CapexScenarioSnapshot:
    snapshot_id: str
    scenario_id: str
    scenario_distribution: dict[str, float]
    dominant_scenario: str
    confidence: float
    data_quality: float
    as_of_date: date
    parameter_version: str
    model_version: str
    reason_codes: list[ReasonItem] = field(default_factory=list)
    warnings: list[WarningItem] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.snapshot_id, "snapshot_id")
        _require_text(self.scenario_id, "scenario_id")
        _require_text(self.dominant_scenario, "dominant_scenario")
        _require_versions(self)
        _require_ratio(self.confidence, "confidence")
        _require_ratio(self.data_quality, "data_quality")

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass(frozen=True)
class CapexValuationSnapshot:
    snapshot_id: str
    asset_id: str
    confidence: float
    data_quality: float
    as_of_date: date
    parameter_version: str
    model_version: str
    fair_value: float | None = None
    current_price: float | None = None
    fair_value_ratio: float | None = None
    target_per: float | None = None
    reason_codes: list[ReasonItem] = field(default_factory=list)
    warnings: list[WarningItem] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.snapshot_id, "snapshot_id")
        _require_text(self.asset_id, "asset_id")
        _require_versions(self)
        _require_ratio(self.confidence, "confidence")
        _require_ratio(self.data_quality, "data_quality")

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass(frozen=True)
class CapexDecisionAuditRow:
    audit_id: str
    snapshot_id: str
    as_of_date: date
    decision_type: str
    parameter_version: str
    model_version: str
    data_quality: float
    reason_codes: list[ReasonItem] = field(default_factory=list)
    warnings: list[WarningItem] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.audit_id, "audit_id")
        _require_text(self.snapshot_id, "snapshot_id")
        _require_text(self.decision_type, "decision_type")
        _require_versions(self)
        _require_ratio(self.data_quality, "data_quality")

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


def _require_versions(value: Any) -> None:
    _require_text(value.parameter_version, "parameter_version")
    _require_text(value.model_version, "model_version")
    if value.as_of_date is None:
        raise CapexCycleModelError("as_of_date is required")


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CapexCycleModelError(f"{field_name} must be a non-empty string")


def _require_ratio(value: float, field_name: str) -> None:
    if value is None or not 0.0 <= float(value) <= 1.0:
        raise CapexCycleModelError(f"{field_name} must be between 0.0 and 1.0")


def _to_dict(value: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for item in fields(value):
        field_value = getattr(value, item.name)
        if isinstance(field_value, date):
            payload[item.name] = field_value.isoformat()
        elif item.name == "reason_codes":
            payload[item.name] = [_serialize_reason(reason) for reason in field_value]
        elif item.name == "warnings":
            payload[item.name] = [_serialize_warning(warning) for warning in field_value]
        else:
            payload[item.name] = field_value
    return payload


def _serialize_reason(reason: ReasonItem | dict[str, Any]) -> dict[str, Any]:
    if isinstance(reason, ReasonItem):
        return reason.model_dump(mode="json")
    return dict(reason)


def _serialize_warning(warning: WarningItem | dict[str, Any]) -> dict[str, Any]:
    if isinstance(warning, WarningItem):
        return warning.model_dump(mode="json")
    return dict(warning)
