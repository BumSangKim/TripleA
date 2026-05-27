import sqlite3
from datetime import UTC, date, datetime
from decimal import Decimal

from api.data.models import CurrentQuote, DataQualityCheck, MacroObservation, PriceBar
from api.data.repository import (
    count_rows,
    read_historical_prices,
    read_latest_data_quality,
    read_latest_quote,
    read_macro_observations,
    upsert_current_quote,
    upsert_macro_rows,
    upsert_price_rows,
    upsert_quality_check,
)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _bar(close: str = "100") -> PriceBar:
    now = datetime(2026, 5, 27, tzinfo=UTC)
    return PriceBar(
        symbol="360750",
        market="KRX",
        date=date(2026, 5, 26),
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        volume=Decimal("1000"),
        source="mock",
        as_of_date=date(2026, 5, 27),
        updated_at=now,
    )


def test_raw_market_price_upsert_is_idempotent_and_readable():
    conn = _conn()

    upsert_price_rows([_bar()], db_session=conn)
    upsert_price_rows([_bar("101")], db_session=conn)
    rows = read_historical_prices(
        symbol="360750",
        market="KRX",
        start_date="2026-05-01",
        end_date="2026-05-31",
        db_session=conn,
    )

    assert count_rows("raw_market_prices", conn) == 1
    assert rows[0]["close"] == Decimal("101")


def test_raw_current_quote_latest_readback():
    conn = _conn()
    now = datetime(2026, 5, 27, 9, tzinfo=UTC)
    quote = CurrentQuote(
        symbol="360750",
        market="KRX",
        price=Decimal("10000"),
        currency="KRW",
        quote_time=now,
        source="mock",
        as_of_date=date(2026, 5, 27),
        updated_at=now,
    )

    upsert_current_quote(quote, db_session=conn)
    saved = read_latest_quote(symbol="360750", market="KRX", db_session=conn)

    assert saved is not None
    assert saved["price"] == Decimal("10000")


def test_macro_rows_and_data_quality_round_trip():
    conn = _conn()
    now = datetime(2026, 5, 27, tzinfo=UTC)
    macro = MacroObservation(
        indicator_key="CPIAUCSL",
        date=date(2026, 4, 30),
        value=Decimal("3.1"),
        unit="%",
        source="mock",
        as_of_date=date(2026, 5, 27),
        release_date=date(2026, 5, 10),
        updated_at=now,
    )
    quality = DataQualityCheck(
        dataset_key="macro:CPIAUCSL",
        source="mock",
        as_of_date=date(2026, 5, 27),
        quality_score=0.95,
        missing_ratio=0.0,
        is_stale=False,
        warnings=[],
        fallback_policy="reduce_signal_weight",
        updated_at=now,
    )

    upsert_macro_rows([macro], db_session=conn)
    upsert_quality_check(quality, db_session=conn)

    observations = read_macro_observations(
        indicator_key="CPIAUCSL",
        start_date="2026-01-01",
        end_date="2026-12-31",
        db_session=conn,
    )
    saved_quality = read_latest_data_quality(dataset_key="macro:CPIAUCSL", db_session=conn)

    assert observations[0]["value"] == Decimal("3.1")
    assert saved_quality["quality_score"] == 0.95
    assert saved_quality["warnings"] == []
