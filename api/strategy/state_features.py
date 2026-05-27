from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MarketStateFeatures:
    market_stress_score: float
    market_adaptation_score: float
    volatility_score: float
    drawdown_score: float
    momentum_score: float
    breadth_score: float | None = None
    correlation_stress_score: float | None = None


@dataclass(frozen=True)
class PortfolioStateFeatures:
    portfolio_vulnerability_score: float
    concentration_score: float
    risk_asset_weight: float
    sector_exposure_summary: dict[str, float] = field(default_factory=dict)
    drawdown_pressure_score: float = 0.5
