from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

PLUGIN_HEALTH_STATUSES = {"OK", "DEGRADED", "FAILED", "RATE_LIMITED", "TIMEOUT", "DISABLED"}


class PluginBoundaryContractError(ValueError):
    pass


@dataclass(frozen=True)
class PluginDataset:
    dataset_id: str
    dataset_type: str
    plugin_id: str
    provider: str
    source: str
    entity_type: str
    entity_id: str | None
    data: Any
    schema_version: str
    as_of_date: date
    available_at: datetime
    retrieved_at: datetime
    quality_score: float
    missing_ratio: float
    is_stale: bool
    warnings: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.dataset_id, "dataset_id")
        _require_text(self.dataset_type, "dataset_type")
        _require_text(self.plugin_id, "plugin_id")
        _require_text(self.provider, "provider")
        _require_text(self.source, "source")
        _require_text(self.entity_type, "entity_type")
        _require_text(self.schema_version, "schema_version")
        if self.available_at is None:
            raise PluginBoundaryContractError("available_at is required")
        if self.retrieved_at is None:
            raise PluginBoundaryContractError("retrieved_at is required")
        _require_ratio(self.quality_score, "quality_score")
        _require_ratio(self.missing_ratio, "missing_ratio")
        if self.plugin_id == self.dataset_type:
            raise PluginBoundaryContractError("plugin_id is trace metadata and must not stand in for dataset_type")


@dataclass(frozen=True)
class PluginQualityScore:
    plugin_id: str
    dataset_id: str | None
    dataset_type: str | None
    quality_score: float
    missing_ratio: float
    freshness_score: float | None
    schema_valid: bool
    is_stale: bool
    fallback_used: bool
    source_priority: int | None
    reason_codes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    measured_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_text(self.plugin_id, "plugin_id")
        if self.dataset_id is not None:
            _require_text(self.dataset_id, "dataset_id")
        if self.dataset_type is not None:
            _require_text(self.dataset_type, "dataset_type")
        _require_ratio(self.quality_score, "quality_score")
        _require_ratio(self.missing_ratio, "missing_ratio")
        if self.freshness_score is not None:
            _require_ratio(self.freshness_score, "freshness_score")
        if self.source_priority is not None and int(self.source_priority) < 0:
            raise PluginBoundaryContractError("source_priority must be non-negative")
        if self.measured_at is None:
            raise PluginBoundaryContractError("measured_at is required")


@dataclass(frozen=True)
class PluginHealthStatus:
    plugin_id: str
    status: str
    last_success_at: datetime | None
    last_failure_at: datetime | None
    error_code: str | None
    error_message: str | None
    latency_ms: int | None
    checked_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.plugin_id, "plugin_id")
        if self.status not in PLUGIN_HEALTH_STATUSES:
            raise PluginBoundaryContractError(f"status must be one of {sorted(PLUGIN_HEALTH_STATUSES)}")
        if self.checked_at is None:
            raise PluginBoundaryContractError("checked_at is required")
        if self.latency_ms is not None and int(self.latency_ms) < 0:
            raise PluginBoundaryContractError("latency_ms must be non-negative")
        if self.status in {"FAILED", "RATE_LIMITED", "TIMEOUT"} and not self.error_code:
            raise PluginBoundaryContractError("error_code is required for failed plugin health states")


@dataclass(frozen=True)
class PluginRunMetadata:
    plugin_id: str
    run_id: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    health: PluginHealthStatus
    quality: PluginQualityScore | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.plugin_id, "plugin_id")
        _require_text(self.run_id, "run_id")
        if self.started_at is None:
            raise PluginBoundaryContractError("started_at is required")
        if self.status not in PLUGIN_HEALTH_STATUSES:
            raise PluginBoundaryContractError(f"status must be one of {sorted(PLUGIN_HEALTH_STATUSES)}")
        if self.health.plugin_id != self.plugin_id:
            raise PluginBoundaryContractError("run metadata health.plugin_id must match plugin_id")
        if self.quality is not None and self.quality.plugin_id != self.plugin_id:
            raise PluginBoundaryContractError("run metadata quality.plugin_id must match plugin_id")


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PluginBoundaryContractError(f"{field_name} must be a non-empty string")


def _require_ratio(value: float, field_name: str) -> None:
    if not 0.0 <= float(value) <= 1.0:
        raise PluginBoundaryContractError(f"{field_name} must be between 0.0 and 1.0")
