from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class AllocationTarget:
    asset_class: str
    asset_code: str
    currency: str
    target_weight: float
    bucket: str | None = None


@dataclass(frozen=True)
class AllocationDecision:
    as_of_date: date
    strategy_mode: str
    risk_profile: str
    universe_id: str
    macro_regime: str
    macro_score: int
    bucket_weights: dict[str, float]
    final_weights: dict[str, float]
    reasons: list[str]
    bottleneck_scores: dict[str, float] = field(default_factory=dict)
    sector_scores: list[SectorBottleneckScore] = field(default_factory=list)


@dataclass(frozen=True)
class SectorBottleneckScore:
    sector_code: str
    total_score: float
    trade_score: float
    demand_score: float
    supply_score: float
    relative_strength_score: float
    regime: str
    reasons: list[str] = field(default_factory=list)
