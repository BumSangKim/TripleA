from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import date, datetime
from enum import StrEnum
from typing import Any


class CapexFetchJobContractError(ValueError):
    pass


class CapexFetchStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class CapexFetchJobRequest:
    source_id: str
    metric_ids: tuple[str, ...]
    start_date: date
    end_date: date
    requested_at: datetime
    dry_run: bool = True
    request_id: str | None = None
    as_of: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.source_id, "source_id")
        if not self.metric_ids:
            raise CapexFetchJobContractError("metric_ids must not be empty")
        for metric_id in self.metric_ids:
            _require_text(metric_id, "metric_id")
        if self.start_date is None:
            raise CapexFetchJobContractError("start_date is required")
        if self.end_date is None:
            raise CapexFetchJobContractError("end_date is required")
        if self.start_date > self.end_date:
            raise CapexFetchJobContractError("start_date must be on or before end_date")
        if self.requested_at is None:
            raise CapexFetchJobContractError("requested_at is required")
        object.__setattr__(self, "metric_ids", tuple(self.metric_ids))
        object.__setattr__(self, "dry_run", bool(self.dry_run))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapexFetchJobRequest":
        return cls(
            source_id=str(data["source_id"]),
            metric_ids=tuple(str(metric_id) for metric_id in data["metric_ids"]),
            start_date=_date(data["start_date"]),
            end_date=_date(data["end_date"]),
            requested_at=_datetime(data["requested_at"]),
            dry_run=bool(data.get("dry_run", True)),
            request_id=data.get("request_id"),
            as_of=_optional_datetime(data.get("as_of")),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class CapexFetchJobResult:
    request_id: str | None
    source_id: str
    metric_ids: tuple[str, ...]
    status: CapexFetchStatus
    dry_run: bool
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    rows_fetched: int = 0
    rows_stored: int = 0
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.source_id, "source_id")
        if not self.metric_ids:
            raise CapexFetchJobContractError("metric_ids must not be empty")
        for metric_id in self.metric_ids:
            _require_text(metric_id, "metric_id")
        if self.requested_at is None:
            raise CapexFetchJobContractError("requested_at is required")
        status = _status(self.status)
        rows_fetched = int(self.rows_fetched)
        rows_stored = int(self.rows_stored)
        if rows_fetched < 0:
            raise CapexFetchJobContractError("rows_fetched must be non-negative")
        if rows_stored < 0:
            raise CapexFetchJobContractError("rows_stored must be non-negative")
        if self.started_at is not None and self.finished_at is not None and self.finished_at < self.started_at:
            raise CapexFetchJobContractError("finished_at must be on or after started_at")
        object.__setattr__(self, "metric_ids", tuple(self.metric_ids))
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "dry_run", bool(self.dry_run))
        object.__setattr__(self, "rows_fetched", rows_fetched)
        object.__setattr__(self, "rows_stored", rows_stored)
        object.__setattr__(self, "warnings", tuple(str(warning) for warning in self.warnings))
        object.__setattr__(self, "errors", tuple(str(error) for error in self.errors))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapexFetchJobResult":
        return cls(
            request_id=data.get("request_id"),
            source_id=str(data["source_id"]),
            metric_ids=tuple(str(metric_id) for metric_id in data["metric_ids"]),
            status=_status(data["status"]),
            dry_run=bool(data.get("dry_run", True)),
            requested_at=_datetime(data["requested_at"]),
            started_at=_optional_datetime(data.get("started_at")),
            finished_at=_optional_datetime(data.get("finished_at")),
            rows_fetched=int(data.get("rows_fetched", 0)),
            rows_stored=int(data.get("rows_stored", 0)),
            warnings=tuple(str(warning) for warning in data.get("warnings", ())),
            errors=tuple(str(error) for error in data.get("errors", ())),
            metadata=dict(data.get("metadata") or {}),
        )


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CapexFetchJobContractError(f"{field_name} must be a non-empty string")


def _status(value: CapexFetchStatus | str) -> CapexFetchStatus:
    try:
        return value if isinstance(value, CapexFetchStatus) else CapexFetchStatus(str(value))
    except ValueError as exc:
        raise CapexFetchJobContractError("status must be a valid CapexFetchStatus") from exc


def _to_dict(value: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for item in fields(value):
        field_value = getattr(value, item.name)
        if isinstance(field_value, datetime):
            payload[item.name] = field_value.isoformat()
        elif isinstance(field_value, date):
            payload[item.name] = field_value.isoformat()
        elif isinstance(field_value, CapexFetchStatus):
            payload[item.name] = field_value.value
        elif isinstance(field_value, tuple):
            payload[item.name] = list(field_value)
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


def _optional_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    return _datetime(value)
