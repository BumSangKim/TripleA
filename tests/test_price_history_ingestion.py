import sqlite3
from datetime import date

from api.data.ingestion import collect_price_history
from api.data.providers import MockMarketDataProvider
from api.data.repository import count_rows, read_historical_prices, read_latest_data_quality
from api.data.source_registry import load_data_sources


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _price_source():
    return [source for source in load_data_sources() if source.source_type == "market_price"][0]


def test_mock_price_history_ingestion_saves_and_reads_back():
    conn = _conn()
    source = _price_source()

    result = collect_price_history(
        source=source,
        start_date=date(2026, 5, 26),
        end_date=date(2026, 5, 27),
        db_session=conn,
    )

    rows = read_historical_prices(
        symbol=source.symbols_or_indicators[0],
        market="KRX",
        start_date="2026-05-26",
        end_date="2026-05-27",
        db_session=conn,
    )
    assert result.status == "success"
    assert result.row_count == 4
    assert len(rows) == 2


def test_price_history_ingestion_is_idempotent():
    conn = _conn()
    source = _price_source()

    for _ in range(2):
        collect_price_history(
            source=source,
            start_date=date(2026, 5, 26),
            end_date=date(2026, 5, 27),
            db_session=conn,
        )

    assert count_rows("raw_market_prices", conn) == 4


def test_empty_price_history_records_quality_warning():
    conn = _conn()
    source = _price_source()

    result = collect_price_history(
        source=source,
        start_date=date(2026, 5, 26),
        end_date=date(2026, 5, 27),
        provider=MockMarketDataProvider(empty=True),
        db_session=conn,
    )
    quality = read_latest_data_quality(dataset_key=f"market_price:{source.source_id}", db_session=conn)

    assert result.status == "empty"
    assert "missing_data" in quality["warnings"]
    assert quality["fallback_policy"] == "use_conservative_fallback"
