from __future__ import annotations

from dataclasses import dataclass

from api.strategy.adaptive_offsets import AdaptiveOffsets, AdaptivePermissions, FrictionOffsets, RiskOffsets, SpeedOffsets, ALLOW, BLOCK, LIMIT
from api.strategy.macro_distribution import MacroRegimeDistribution
from api.strategy.state_features import MarketStateFeatures, PortfolioStateFeatures
from api.strategy.score_contract import clamp_score


@dataclass(frozen=True)
class RegimeResponseDecision:
    response_mode: str
    response_urgency: float
    macro_change_score: float
    market_stress_score: float
    market_adaptation_score: float
    portfolio_vulnerability_score: float
    confidence: float
    data_quality: float
    offsets: AdaptiveOffsets
    permissions: AdaptivePermissions
    reason_codes: list[str]
    model_version: str = "regime_response_v1"
    parameter_version: str = "default"


class RegimeResponseEngine:
    def decide(
        self,
        macro: MacroRegimeDistribution,
        market: MarketStateFeatures,
        portfolio: PortfolioStateFeatures,
    ) -> RegimeResponseDecision:
        stress = clamp_score((macro.distribution.get("volatility_stress", 0.0) + market.market_stress_score + portfolio.portfolio_vulnerability_score) / 3)
        adaptation = clamp_score(market.market_adaptation_score)
        urgency = clamp_score(stress * 0.7 + macro.macro_change_speed * 0.3)
        if stress > 0.7:
            mode = "DEFEND"
            permissions = AdaptivePermissions(sector_expansion=BLOCK, forced_sell=ALLOW, new_risk_buy=BLOCK)
            risk = RiskOffsets(aggressive_alpha_max_offset=-0.10, defensive_core_min_offset=0.05, liquidity_min_offset=0.05)
        elif adaptation > 0.65 and stress < 0.5:
            mode = "ADAPT"
            permissions = AdaptivePermissions(sector_expansion=LIMIT, forced_sell=LIMIT, new_risk_buy=LIMIT)
            risk = RiskOffsets(sector_pressure_cap_offset=0.03)
        else:
            mode = "OBSERVE"
            permissions = AdaptivePermissions()
            risk = RiskOffsets()
        offsets = AdaptiveOffsets(risk=risk, speed=SpeedOffsets(target_adjustment_speed_multiplier=1.0 + urgency * 0.5), friction=FrictionOffsets(rebalance_band_offset=max(0.0, 0.02 - urgency * 0.01)))
        return RegimeResponseDecision(
            response_mode=mode,
            response_urgency=urgency,
            macro_change_score=macro.macro_change_score,
            market_stress_score=market.market_stress_score,
            market_adaptation_score=market.market_adaptation_score,
            portfolio_vulnerability_score=portfolio.portfolio_vulnerability_score,
            confidence=min(macro.confidence, 1.0 - stress * 0.2),
            data_quality=macro.data_quality,
            offsets=offsets,
            permissions=permissions,
            reason_codes=[f"mode:{mode}", f"stress:{stress:.2f}"],
        )
