from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime
from typing import Any

from api.features.backtests.sector_component_models import (
    CONSERVATIVE_FALLBACK_STATES,
    SectorComponentBacktestResult,
    SectorComponentValidationWarning,
)


SECTOR_COMPONENT_SCOPE_SEMANTICS = "independent_enabled_sector_backtests"
SECTOR_COMPONENT_SCOPE_MODES = {"all", "single"}


@dataclass(frozen=True)
class SectorComponentScope:
    mode: str
    sector_id: str | None = None

    def __post_init__(self) -> None:
        mode = self.mode.strip().lower() if isinstance(self.mode, str) else self.mode
        if mode not in SECTOR_COMPONENT_SCOPE_MODES:
            raise ValueError("sector component scope mode must be all or single")
        object.__setattr__(self, "mode", mode)
        if mode == "all" and self.sector_id is not None:
            raise ValueError("all sector scope must not include sector_id")
        if mode == "single" and not (isinstance(self.sector_id, str) and self.sector_id.strip()):
            raise ValueError("single sector scope requires sector_id")
        if isinstance(self.sector_id, str):
            object.__setattr__(self, "sector_id", self.sector_id.strip())

    def to_dict(self) -> dict[str, Any]:
        return _serialize_dataclass(self)


@dataclass(frozen=True)
class SectorComponentComparisonRow:
    sector_id: str
    display_name: str
    portfolio_id: str
    status: str
    total_return: float | None = None
    max_drawdown: float | None = None
    volatility: float | None = None
    hit_rate: float | None = None
    observation_count: int = 0
    warning_count: int = 0
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[SectorComponentValidationWarning, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.status not in CONSERVATIVE_FALLBACK_STATES | {"OK"}:
            raise ValueError("status must be OK or conservative")
        _coerce_tuple(self, "reason_codes")
        _coerce_tuple(self, "warnings")

    def to_dict(self) -> dict[str, Any]:
        return _serialize_dataclass(self)


@dataclass(frozen=True)
class SectorComponentScopedBacktestResult:
    sector_scope: SectorComponentScope
    parameter_version: str
    model_version: str
    data_snapshot_id: str
    status: str
    semantics: str = SECTOR_COMPONENT_SCOPE_SEMANTICS
    comparison_rows: tuple[SectorComponentComparisonRow, ...] = field(default_factory=tuple)
    sector_results: tuple[SectorComponentBacktestResult, ...] = field(default_factory=tuple)
    warnings: tuple[SectorComponentValidationWarning, ...] = field(default_factory=tuple)
    reason_codes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.semantics != SECTOR_COMPONENT_SCOPE_SEMANTICS:
            raise ValueError("sector scope semantics must be independent_enabled_sector_backtests")
        if self.status not in CONSERVATIVE_FALLBACK_STATES | {"OK"}:
            raise ValueError("status must be OK or conservative")
        _coerce_tuple(self, "comparison_rows")
        _coerce_tuple(self, "sector_results")
        _coerce_tuple(self, "warnings")
        _coerce_tuple(self, "reason_codes")

    def to_dict(self) -> dict[str, Any]:
        return _serialize_dataclass(self)


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
