from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from api.strategy.score_contract import clamp_score, combine_reason_codes
from api.strategy.sector_score_aggregator import AggregatedSectorScore


@dataclass(frozen=True)
class SectorAllocationPressure:
    sector_code: str
    as_of_date: date
    allocation_pressure: float
    previous_allocation_pressure: float | None
    pressure_change: float | None
    opportunity_score: float
    leadership_score: float
    persistence_score: float
    market_adaptation_score: float | None
    risk_penalty_score: float
    valuation_burden_score: float | None
    concentration_penalty_score: float
    confidence: float
    data_quality: float
    reason_codes: list[str]
    model_version: str = "sector_allocation_pressure_v1"
    parameter_version: str = "default"


def compute_sector_allocation_pressure(
    score: AggregatedSectorScore,
    *,
    previous_pressure: float | None = None,
    concentration: float = 0.0,
    risk_penalty: float = 0.0,
    market_adaptation_score: float | None = None,
    valuation_burden_score: float | None = None,
) -> SectorAllocationPressure:
    opportunity = score.total_score
    leadership = score.common_score
    persistence = score.confidence
    adaptation = 0.5 if market_adaptation_score is None else market_adaptation_score
    valuation = 0.0 if valuation_burden_score is None else valuation_burden_score
    raw = (
        opportunity * 0.35
        + leadership * 0.25
        + persistence * 0.15
        + adaptation * 0.10
        - risk_penalty * 0.10
        - valuation * 0.05
        - concentration * 0.15
        - (1.0 - score.data_quality) * 0.20
    )
    pressure = clamp_score(raw)
    return SectorAllocationPressure(
        score.sector_code,
        score.as_of_date,
        pressure,
        previous_pressure,
        None if previous_pressure is None else pressure - previous_pressure,
        opportunity,
        leadership,
        persistence,
        market_adaptation_score,
        risk_penalty,
        valuation_burden_score,
        concentration,
        score.confidence,
        score.data_quality,
        combine_reason_codes(score.reason_codes, ["allocation_pressure_computed"]),
    )
