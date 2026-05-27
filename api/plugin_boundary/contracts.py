from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


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


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PluginBoundaryContractError(f"{field_name} must be a non-empty string")


def _require_ratio(value: float, field_name: str) -> None:
    if not 0.0 <= float(value) <= 1.0:
        raise PluginBoundaryContractError(f"{field_name} must be between 0.0 and 1.0")
