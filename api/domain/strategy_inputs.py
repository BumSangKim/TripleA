from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class MacroIndicatorInput:
    indicator: str
    value: float
    unit: str | None
    data_date: date
    source: str | None


@dataclass(frozen=True)
class MacroSnapshotInput:
    as_of_date: date
    indicators: dict[str, MacroIndicatorInput] = field(default_factory=dict)

    def get_value(self, *keys: str) -> float | None:
        normalized = {key.upper() for key in keys}
        for key, item in self.indicators.items():
            if key.upper() in normalized:
                return item.value
        return None


@dataclass(frozen=True)
class BottleneckIndicatorInput:
    indicator_key: str
    indicator_name: str | None
    sector_code: str
    value_date: date
    release_date: date
    value: float | None
    unit: str | None
    source: str | None
    layer: str | None


@dataclass(frozen=True)
class BottleneckSnapshotInput:
    as_of_date: date
    lookback_months: int
    indicators: list[BottleneckIndicatorInput] = field(default_factory=list)


@dataclass(frozen=True)
class SectorAssetMappingInput:
    sector_code: str
    asset_code: str
    asset_name: str | None
    asset_type: str | None
    currency: str
    priority: int


@dataclass(frozen=True)
class PriceHistoryPointInput:
    asset_code: str
    price_date: date
    price: float


@dataclass(frozen=True)
class StrategyDecisionLogInput:
    decision_id: str
    as_of_date: date
    decision_type: str
    payload: dict[str, Any]
    snapshot_id: str | None = None
    reason_codes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

