import sqlite3
from datetime import date

import pytest

from api.db.initialize import initialize_database as ensure_dashboard_tables
from api.market_data_service import (
    get_asset_universe,
    get_fx_matrix,
    get_price_matrix,
    get_price_on_or_before,
    resolve_asset_class_to_asset_code,
    validate_market_data_coverage,
)


@pytest.fixture()
def market_conn(tmp_path, monkeypatch):
    db_path = str(tmp_path / "market_service.db")
    monkeypatch.setattr("api.db.connection.DB_PATH", db_path)
    ensure_dashboard_tables()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def test_asset_universe_mapping_is_loaded_from_config(market_conn):
    assets = get_asset_universe(market_conn)
    classes = {asset.asset_class: asset.asset_code for asset in assets}

    assert classes["국내주식"] == "KOSPI"
    assert classes["해외주식"] == "SPY"
    assert resolve_asset_class_to_asset_code(market_conn, "채권") == "TLT"


def test_price_and_fx_matrix_use_adjusted_close_when_available(market_conn):
    market_conn.executemany(
        """
        INSERT INTO market_prices
        (asset_code, price_date, close, adj_close, currency, source)
        VALUES (?, ?, ?, ?, ?, 'test')
        """,
        [
            ("SPY", "2024-01-02", 100.0, 101.0, "USD"),
            ("SPY", "2024-01-03", 102.0, None, "USD"),
        ],
    )
    market_conn.executemany(
        """
        INSERT INTO fx_rates
        (base_currency, quote_currency, rate_date, rate, source)
        VALUES ('USD', 'KRW', ?, ?, 'test')
        """,
        [("2024-01-02", 1300.0), ("2024-01-03", 1310.0)],
    )
    market_conn.commit()

    prices = get_price_matrix(market_conn, ["SPY"], date(2024, 1, 2), date(2024, 1, 3))
    fx = get_fx_matrix(market_conn, ["USD"], date(2024, 1, 2), date(2024, 1, 3))

    assert prices["SPY"][date(2024, 1, 2)] == 101.0
    assert prices["SPY"][date(2024, 1, 3)] == 102.0
    assert fx["USD"][date(2024, 1, 3)] == 1310.0


def test_validate_market_data_coverage_checks_price_and_fx(market_conn):
    market_conn.executemany(
        """
        INSERT INTO market_prices
        (asset_code, price_date, close, currency, source)
        VALUES (?, ?, ?, ?, 'test')
        """,
        [
            ("SPY", "2024-01-02", 100.0, "USD"),
            ("SPY", "2024-01-31", 110.0, "USD"),
        ],
    )
    market_conn.executemany(
        """
        INSERT INTO fx_rates
        (base_currency, quote_currency, rate_date, rate, source)
        VALUES ('USD', 'KRW', ?, ?, 'test')
        """,
        [("2024-01-02", 1300.0), ("2024-01-31", 1320.0)],
    )
    market_conn.commit()

    coverage = validate_market_data_coverage(
        market_conn,
        ["SPY", "CASH_KRW"],
        date(2024, 1, 2),
        date(2024, 1, 31),
    )

    assert coverage.ok is True
    assert len(coverage.assets) == 2
    assert coverage.fx_rates[0].base_currency == "USD"


def test_validate_market_data_coverage_reports_missing_fx(market_conn):
    market_conn.executemany(
        """
        INSERT INTO market_prices
        (asset_code, price_date, close, currency, source)
        VALUES ('SPY', ?, ?, 'USD', 'test')
        """,
        [("2024-01-02", 100.0), ("2024-01-31", 110.0)],
    )
    market_conn.commit()

    coverage = validate_market_data_coverage(
        market_conn,
        ["SPY"],
        date(2024, 1, 2),
        date(2024, 1, 31),
    )

    assert coverage.ok is False
    assert "USD/KRW" in coverage.missing_messages[0]


def test_price_lookup_uses_latest_available_price_without_lookahead(market_conn):
    market_conn.executemany(
        """
        INSERT INTO market_prices
        (asset_code, price_date, close, currency, source)
        VALUES ('SPY', ?, ?, 'USD', 'test')
        """,
        [("2024-01-02", 100.0), ("2024-01-04", 120.0)],
    )
    market_conn.commit()

    price_date, price = get_price_on_or_before(market_conn, "SPY", date(2024, 1, 3))

    assert price_date == date(2024, 1, 2)
    assert price == 100.0
