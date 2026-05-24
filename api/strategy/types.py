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
