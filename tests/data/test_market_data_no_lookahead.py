from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from api.db.initialize import initialize_database
from api.market_data_service import (
    get_fx_rate_on_or_before,
    get_price_on_or_before,
    validate_market_data_coverage,
)


@pytest.fixture()
def market_conn(tmp_path, monkeypatch):
    db_path = str(tmp_path / "market_no_lookahead.db")
    monkeypatch.setattr("api.db.connection.DB_PATH", db_path)
    initialize_database()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def test_no_lookahead_coverage_rejects_future_price_and_future_fx(market_conn):
    market_conn.execute(
        """
        INSERT INTO market_prices
        (asset_code, price_date, close, currency, source)
        VALUES ('SPY', '2024-01-03', 101.0, 'USD', 'test')
        """
    )
    market_conn.execute(
        """
        INSERT INTO fx_rates
        (base_currency, quote_currency, rate_date, rate, source)
        VALUES ('USD', 'KRW', '2024-01-03', 1300.0, 'test')
        """
    )
    market_conn.commit()

    coverage = validate_market_data_coverage(
        market_conn,
        ["SPY"],
        date(2024, 1, 2),
        date(2024, 1, 3),
    )

    assert coverage.ok is False
    assert coverage.assets[0].price_start_date != date(2024, 1, 3)


def test_no_lookahead_price_lookup_rejects_future_price(market_conn):
    market_conn.execute(
        """
        INSERT INTO market_prices
        (asset_code, price_date, close, currency, source)
        VALUES ('SPY', '2024-01-03', 101.0, 'USD', 'test')
        """
    )
    market_conn.commit()

    with pytest.raises(KeyError):
        get_price_on_or_before(market_conn, "SPY", date(2024, 1, 2))


def test_no_lookahead_fx_lookup_rejects_future_fx(market_conn):
    market_conn.execute(
        """
        INSERT INTO fx_rates
        (base_currency, quote_currency, rate_date, rate, source)
        VALUES ('USD', 'KRW', '2024-01-03', 1300.0, 'test')
        """
    )
    market_conn.commit()

    with pytest.raises(KeyError):
        get_fx_rate_on_or_before(market_conn, "USD", date(2024, 1, 2))
