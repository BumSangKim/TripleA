from __future__ import annotations

from dataclasses import dataclass, field


Permission = str
ALLOW = "ALLOW"
LIMIT = "LIMIT"
BLOCK = "BLOCK"


@dataclass(frozen=True)
class RiskOffsets:
    aggressive_alpha_max_offset: float = 0.0
    defensive_core_min_offset: float = 0.0
    liquidity_min_offset: float = 0.0
    sector_pressure_cap_offset: float = 0.0
    single_sector_max_offset: float = 0.0


@dataclass(frozen=True)
class SpeedOffsets:
    max_change_per_rebalance_offset: float = 0.0
    target_adjustment_speed_multiplier: float = 1.0


@dataclass(frozen=True)
class FrictionOffsets:
    rebalance_band_offset: float = 0.0
    turnover_limit_offset: float = 0.0
    cost_threshold_offset: float = 0.0


@dataclass(frozen=True)
class AdaptiveOffsets:
    risk: RiskOffsets = field(default_factory=RiskOffsets)
    speed: SpeedOffsets = field(default_factory=SpeedOffsets)
    friction: FrictionOffsets = field(default_factory=FrictionOffsets)


@dataclass(frozen=True)
class AdaptivePermissions:
    sector_expansion: Permission = LIMIT
    forced_sell: Permission = LIMIT
    risk_increase_buy: Permission = LIMIT
