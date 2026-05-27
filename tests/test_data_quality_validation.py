from datetime import UTC, date, datetime
from decimal import Decimal

from api.data.models import PriceBar
from api.data.quality import evaluate_price_quality


def _row(row_date: date, close: str) -> PriceBar:
    now = datetime(2026, 5, 27, tzinfo=UTC)
    price = Decimal(close)
    return PriceBar(
        symbol="360750",
        market="KRX",
        date=row_date,
        open=price,
        high=price,
        low=price,
        close=price,
        volume=Decimal("1000"),
        source="mock",
        as_of_date=date(2026, 5, 27),
        updated_at=now,
    )


def test_normal_price_data_has_high_quality_score():
    check = evaluate_price_quality(
        [_row(date(2026, 5, 26), "100"), _row(date(2026, 5, 27), "101")],
        dataset_key="market_price:test",
        source="mock",
        as_of_date=date(2026, 5, 27),
        expected_points=2,
        stale_after_days=7,
    )

    assert check.quality_score == 1.0
    assert check.missing_ratio == 0.0
    assert check.is_stale is False


def test_missing_data_increases_missing_ratio():
    check = evaluate_price_quality(
        [_row(date(2026, 5, 27), "100")],
        dataset_key="market_price:test",
        source="mock",
        as_of_date=date(2026, 5, 27),
        expected_points=2,
        stale_after_days=7,
    )

    assert check.missing_ratio == 0.5
    assert "missing_data" in check.warnings


def test_old_data_is_marked_stale():
    check = evaluate_price_quality(
        [_row(date(2026, 5, 1), "100")],
        dataset_key="market_price:test",
        source="mock",
        as_of_date=date(2026, 5, 27),
        expected_points=1,
        stale_after_days=7,
    )

    assert check.is_stale is True
    assert "stale_data" in check.warnings


def test_non_positive_price_is_anomaly():
    check = evaluate_price_quality(
        [_row(date(2026, 5, 27), "0")],
        dataset_key="market_price:test",
        source="mock",
        as_of_date=date(2026, 5, 27),
        expected_points=1,
        stale_after_days=7,
    )

    assert "non_positive_price" in check.warnings


def test_poor_quality_uses_conservative_fallback():
    check = evaluate_price_quality(
        [],
        dataset_key="market_price:test",
        source="mock",
        as_of_date=date(2026, 5, 27),
        expected_points=3,
        stale_after_days=7,
        fallback_policy="reduce_signal_weight",
    )

    assert check.quality_score < 0.5
    assert check.fallback_policy == "use_conservative_fallback"
