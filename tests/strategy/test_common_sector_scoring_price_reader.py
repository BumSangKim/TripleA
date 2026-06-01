from __future__ import annotations

from datetime import date

from api.domain.strategy_inputs import PriceHistoryPointInput
from api.strategy.common_sector_scoring_engine import CommonSectorScoringEngine


class FakePriceReader:
    def __init__(self, points: dict[str, list[PriceHistoryPointInput]]):
        self.points = points
        self.calls: list[tuple[str, date, date]] = []

    def read_price_history(
        self,
        asset_code: str,
        *,
        start_date: date,
        end_date: date,
    ) -> list[PriceHistoryPointInput]:
        self.calls.append((asset_code, start_date, end_date))
        return [
            point
            for point in self.points.get(asset_code, [])
            if start_date <= point.price_date <= end_date
        ]


def _point(asset_code: str, price_date: date, price: float) -> PriceHistoryPointInput:
    return PriceHistoryPointInput(asset_code=asset_code, price_date=price_date, price=price)


def test_common_sector_scoring_uses_fake_price_reader_deterministically():
    reader = FakePriceReader({
        "SMH": [_point("SMH", date(2026, 5, 1), 100), _point("SMH", date(2026, 5, 27), 120)],
        "SPY": [_point("SPY", date(2026, 5, 1), 100), _point("SPY", date(2026, 5, 27), 105)],
    })

    score = CommonSectorScoringEngine(reader).score_sector(
        "SEMICONDUCTOR",
        "SMH",
        "SPY",
        date(2026, 5, 27),
    )

    assert score.momentum_score > 0.5
    assert score.relative_strength_score > 0.5
    assert score.drawdown_penalty_score == 0.0
    assert 0 <= score.total_common_score <= 1
    assert reader.calls == [
        ("SMH", date.min, date(2026, 5, 27)),
        ("SPY", date.min, date(2026, 5, 27)),
    ]


def test_common_sector_scoring_missing_history_returns_conservative_fallback():
    score = CommonSectorScoringEngine(FakePriceReader({})).score_sector(
        "SEMICONDUCTOR",
        "SMH",
        "SPY",
        date(2026, 5, 27),
    )

    assert score.total_common_score == 0.5
    assert score.confidence == 0.25
    assert score.reason_codes == ["insufficient_price_history"]


def test_common_sector_scoring_reader_boundary_excludes_future_prices():
    reader = FakePriceReader({
        "SMH": [
            _point("SMH", date(2026, 5, 1), 100),
            _point("SMH", date(2026, 5, 27), 120),
            _point("SMH", date(2026, 6, 1), 200),
        ],
        "SPY": [_point("SPY", date(2026, 5, 1), 100), _point("SPY", date(2026, 5, 27), 105)],
    })

    score = CommonSectorScoringEngine(reader).score_sector(
        "SEMICONDUCTOR",
        "SMH",
        "SPY",
        date(2026, 5, 27),
    )

    assert score.momentum_score < 1.0

