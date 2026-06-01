from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from api.strategy.data_ports import PriceHistoryReader
from api.strategy.score_contract import clamp_score, safe_weighted_average, ScoreComponent, combine_reason_codes


@dataclass(frozen=True)
class CommonSectorScore:
    sector_code: str
    as_of_date: date
    momentum_score: float
    relative_strength_score: float
    persistence_score: float
    volatility_penalty_score: float
    drawdown_penalty_score: float
    valuation_burden_score: float | None
    liquidity_score: float
    earnings_score: float | None
    data_quality: float
    confidence: float
    total_common_score: float
    reason_codes: list[str]


class CommonSectorScoringEngine:
    def __init__(self, price_reader: PriceHistoryReader | None = None):
        self.price_reader = price_reader

    def score_sector(self, sector_code: str, benchmark_asset_code: str | None, market_asset_code: str | None, as_of_date: date) -> CommonSectorScore:
        if not benchmark_asset_code:
            return _conservative(sector_code, as_of_date, ["missing_benchmark"])
        prices = _prices(self.price_reader, benchmark_asset_code, as_of_date)
        market_prices = _prices(self.price_reader, market_asset_code, as_of_date) if market_asset_code else []
        if len(prices) < 2:
            return _conservative(sector_code, as_of_date, ["insufficient_price_history"])
        momentum = clamp_score(0.5 + (_return(prices) / 0.4))
        relative = clamp_score(0.5 + ((_return(prices) - _return(market_prices)) / 0.4)) if len(market_prices) >= 2 else 0.5
        volatility = min(_volatility_penalty(prices), 1.0)
        drawdown = min(_drawdown_penalty(prices), 1.0)
        liquidity = 0.7
        confidence = 0.75 if market_prices else 0.6
        components = [
            ScoreComponent("momentum", momentum, 0.30, 0, ["momentum"]),
            ScoreComponent("relative_strength", relative, 0.30, 0, ["relative_strength"]),
            ScoreComponent("persistence", momentum, 0.15, 0, ["persistence"]),
            ScoreComponent("volatility_penalty", 1 - volatility, 0.10, 0, ["volatility_penalty"]),
            ScoreComponent("drawdown_penalty", 1 - drawdown, 0.10, 0, ["drawdown_penalty"]),
            ScoreComponent("liquidity", liquidity, 0.05, 0, ["liquidity_proxy"]),
        ]
        total = safe_weighted_average(components)
        return CommonSectorScore(
            sector_code=sector_code,
            as_of_date=as_of_date,
            momentum_score=momentum,
            relative_strength_score=relative,
            persistence_score=momentum,
            volatility_penalty_score=volatility,
            drawdown_penalty_score=drawdown,
            valuation_burden_score=None,
            liquidity_score=liquidity,
            earnings_score=None,
            data_quality=confidence,
            confidence=confidence - 0.1,
            total_common_score=total,
            reason_codes=combine_reason_codes(["missing_valuation", "missing_earnings"], *[c.reason_codes for c in components]),
        )


def _conservative(sector_code: str, as_of_date: date, reasons: list[str]) -> CommonSectorScore:
    return CommonSectorScore(sector_code, as_of_date, 0.5, 0.5, 0.5, 0.5, 0.5, None, 0.5, None, 0.3, 0.25, 0.5, reasons)


def _prices(price_reader: PriceHistoryReader | None, asset_code: str | None, as_of_date: date) -> list[float]:
    if not asset_code or price_reader is None or not hasattr(price_reader, "read_price_history"):
        return []
    points = price_reader.read_price_history(
        asset_code,
        start_date=date.min,
        end_date=as_of_date,
    )
    return [float(point.price) for point in points if point.price_date <= as_of_date]


def _return(prices: list[float]) -> float:
    if len(prices) < 2 or prices[0] <= 0:
        return 0.0
    return prices[-1] / prices[0] - 1.0


def _volatility_penalty(prices: list[float]) -> float:
    returns = [prices[i] / prices[i - 1] - 1 for i in range(1, len(prices)) if prices[i - 1] > 0]
    if not returns:
        return 0.5
    mean = sum(returns) / len(returns)
    variance = sum((item - mean) ** 2 for item in returns) / len(returns)
    return clamp_score((variance ** 0.5) * 10)


def _drawdown_penalty(prices: list[float]) -> float:
    peak = prices[0]
    max_dd = 0.0
    for price in prices:
        peak = max(peak, price)
        if peak > 0:
            max_dd = min(max_dd, price / peak - 1)
    return clamp_score(abs(max_dd) * 3)
