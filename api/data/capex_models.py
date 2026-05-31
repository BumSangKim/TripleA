from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import date, datetime
from decimal import Decimal
from typing import Any


CONSERVATIVE_FALLBACK_STATES = {"NO_ACTION", "HOLD", "REVIEW_REQUIRED", "RISK_REDUCE_ONLY"}


class CapexRawDataModelError(ValueError):
    pass


@dataclass(frozen=True)
class RawTimeSeriesPoint:
    source: str
    source_id: str
    metric_id: str
    observation_date: date
    value: Decimal
    unit: str
    available_at: datetime
    updated_at: datetime
    revision_id: str | None = None
    source_priority: int = 0
    confidence: float = 1.0
    license_class: str = "public"
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_common(self)
        if self.observation_date is None:
            raise CapexRawDataModelError("observation_date is required")
        if self.value is None:
            raise CapexRawDataModelError("value is required")
        _require_ratio(self.confidence, "confidence")
        if int(self.source_priority) < 0:
            raise CapexRawDataModelError("source_priority must be non-negative")
        object.__setattr__(self, "value", Decimal(str(self.value)))

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RawTimeSeriesPoint":
        return cls(
            source=str(data["source"]),
            source_id=str(data["source_id"]),
            metric_id=str(data["metric_id"]),
            observation_date=_date(data["observation_date"]),
            value=Decimal(str(data["value"])),
            unit=str(data["unit"]),
            available_at=_datetime(data["available_at"]),
            updated_at=_datetime(data["updated_at"]),
            revision_id=data.get("revision_id"),
            source_priority=int(data.get("source_priority", 0)),
            confidence=float(data.get("confidence", 1.0)),
            license_class=str(data.get("license_class", "public")),
            attributes=dict(data.get("attributes") or {}),
        )


@dataclass(frozen=True)
class RawCompanyMetricPoint:
    source: str
    source_id: str
    company_id: str
    metric_id: str
    period: str
    value: Decimal
    unit: str
    available_at: datetime
    updated_at: datetime
    revision_id: str | None = None
    source_priority: int = 0
    confidence: float = 1.0
    license_class: str = "public"
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_common(self)
        _require_text(self.company_id, "company_id")
        _require_text(self.period, "period")
        if self.value is None:
            raise CapexRawDataModelError("value is required")
        _require_ratio(self.confidence, "confidence")
        if int(self.source_priority) < 0:
            raise CapexRawDataModelError("source_priority must be non-negative")
        object.__setattr__(self, "value", Decimal(str(self.value)))

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RawCompanyMetricPoint":
        return cls(
            source=str(data["source"]),
            source_id=str(data["source_id"]),
            company_id=str(data["company_id"]),
            metric_id=str(data["metric_id"]),
            period=str(data["period"]),
            value=Decimal(str(data["value"])),
            unit=str(data["unit"]),
            available_at=_datetime(data["available_at"]),
            updated_at=_datetime(data["updated_at"]),
            revision_id=data.get("revision_id"),
            source_priority=int(data.get("source_priority", 0)),
            confidence=float(data.get("confidence", 1.0)),
            license_class=str(data.get("license_class", "public")),
            attributes=dict(data.get("attributes") or {}),
        )


@dataclass(frozen=True)
class SourceFetchLogRecord:
    fetch_id: str
    source_id: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    row_count: int
    metric_ids: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    license_class: str = "public"

    def __post_init__(self) -> None:
        _require_text(self.fetch_id, "fetch_id")
        _require_text(self.source_id, "source_id")
        _require_text(self.status, "status")
        if self.started_at is None:
            raise CapexRawDataModelError("started_at is required")
        if int(self.row_count) < 0:
            raise CapexRawDataModelError("row_count must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass(frozen=True)
class DataQualityIssueRecord:
    issue_id: str
    source_id: str
    metric_id: str
    severity: str
    reason_code: str
    message: str
    as_of_date: date
    available_at: datetime
    updated_at: datetime
    fallback_state: str = "REVIEW_REQUIRED"
    confidence: float = 0.0
    license_class: str = "public"

    def __post_init__(self) -> None:
        _require_text(self.issue_id, "issue_id")
        _require_text(self.source_id, "source_id")
        _require_text(self.metric_id, "metric_id")
        _require_text(self.reason_code, "reason_code")
        _require_text(self.message, "message")
        _require_text(self.license_class, "license_class")
        if self.available_at is None:
            raise CapexRawDataModelError("available_at is required")
        if self.updated_at is None:
            raise CapexRawDataModelError("updated_at is required")
        if self.severity not in {"INFO", "WARNING", "ERROR", "BLOCKER"}:
            raise CapexRawDataModelError("severity must be INFO, WARNING, ERROR, or BLOCKER")
        if self.fallback_state not in CONSERVATIVE_FALLBACK_STATES:
            raise CapexRawDataModelError("fallback_state must be conservative")
        if self.as_of_date is None:
            raise CapexRawDataModelError("as_of_date is required")
        _require_ratio(self.confidence, "confidence")

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


def _require_common(value: Any) -> None:
    _require_text(value.source, "source")
    _require_text(value.source_id, "source_id")
    _require_text(value.metric_id, "metric_id")
    _require_text(value.unit, "unit")
    _require_text(value.license_class, "license_class")
    if value.available_at is None:
        raise CapexRawDataModelError("available_at is required")
    if value.updated_at is None:
        raise CapexRawDataModelError("updated_at is required")


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CapexRawDataModelError(f"{field_name} must be a non-empty string")


def _require_ratio(value: float, field_name: str) -> None:
    if value is None or not 0.0 <= float(value) <= 1.0:
        raise CapexRawDataModelError(f"{field_name} must be between 0.0 and 1.0")


def _to_dict(value: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for item in fields(value):
        field_value = getattr(value, item.name)
        if isinstance(field_value, datetime):
            payload[item.name] = field_value.isoformat()
        elif isinstance(field_value, date):
            payload[item.name] = field_value.isoformat()
        elif isinstance(field_value, Decimal):
            payload[item.name] = str(field_value)
        else:
            payload[item.name] = field_value
    return payload


def _date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))
