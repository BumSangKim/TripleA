from datetime import date

from api.strategy.sector_allocation_pressure import compute_sector_allocation_pressure
from api.strategy.sector_score_aggregator import AggregatedSectorScore


def test_sector_allocation_pressure_responds_to_score_and_risk():
    strong = AggregatedSectorScore("S", date(2026, 5, 27), .8, {}, {}, .8, .8, .9, ["strong"])
    weak_quality = AggregatedSectorScore("S", date(2026, 5, 27), .8, {}, {}, .8, .8, .2, ["weak_quality"])
    high = compute_sector_allocation_pressure(strong)
    concentrated = compute_sector_allocation_pressure(strong, concentration=.8, risk_penalty=.5)
    poor = compute_sector_allocation_pressure(weak_quality)
    assert high.allocation_pressure > concentrated.allocation_pressure
    assert poor.allocation_pressure < high.allocation_pressure
    assert 0 <= high.allocation_pressure <= 1
