import sqlite3
from datetime import date

import pytest

from api.backtest_engine import BacktestConfig, BacktestEngine
from api.db import ensure_dashboard_tables
from api.strategy_allocator import StaticTargetAllocator


@pytest.fixture()
def engine_conn(tmp_path, monkeypatch):
    db_path = str(tmp_path / "engine.db")
    monkeypatch.setattr("api.db.DB_PATH", db_path)
    ensure_dashboard_tables()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def _seed_spy_prices_and_fx(conn: sqlite3.Connection):
    conn.executemany(
        """
        INSERT INTO market_prices
        (asset_code, price_date, close, currency, source)
        VALUES ('SPY', ?, ?, 'USD', 'test')
        """,
        [
            ("2024-01-02", 100.0),
            ("2024-01-03", 110.0),
            ("2024-01-04", 120.0),
        ],
    )
    conn.executemany(
        """
        INSERT INTO fx_rates
        (base_currency, quote_currency, rate_date, rate, source)
        VALUES ('USD', 'KRW', ?, 1000.0, 'test')
        """,
        [("2024-01-02",), ("2024-01-03",), ("2024-01-04",)],
    )
    conn.commit()


def test_static_allocator_maps_asset_class_targets_to_asset_codes(engine_conn):
    targets = StaticTargetAllocator(engine_conn).allocate({"해외주식": 70, "현금": 30})

    assert [(target.asset_code, target.target_weight) for target in targets] == [
        ("SPY", 0.7),
        ("CASH_KRW", 0.3),
    ]


def test_backtest_engine_values_portfolio_with_prices_and_fx(engine_conn):
    _seed_spy_prices_and_fx(engine_conn)

    result = BacktestEngine(engine_conn).run(
        BacktestConfig(
            start_date=date(2024, 1, 2),
            end_date=date(2024, 1, 4),
            initial_capital=100_000,
            rebalance_frequency="monthly",
            target_weights={"해외주식": 0.5, "현금": 0.5},
        )
    )

    assert [point.point_date for point in result.points] == [
        date(2024, 1, 2),
        date(2024, 1, 3),
        date(2024, 1, 4),
    ]
    assert result.points[0].portfolio_value == 100_000
    assert result.points[-1].portfolio_value == 110_000
    assert result.total_return == 10.0
    assert result.max_drawdown == 0.0
    assert len(result.trades) == 2
    assert {trade.asset_code for trade in result.trades} == {"SPY", "CASH_KRW"}
    assert any(position.asset_code == "SPY" and position.market_value == 60_000 for position in result.positions)


def test_backtest_engine_rejects_missing_market_coverage(engine_conn):
    engine_conn.executemany(
        """
        INSERT INTO market_prices
        (asset_code, price_date, close, currency, source)
        VALUES ('SPY', ?, ?, 'USD', 'test')
        """,
        [("2024-01-02", 100.0), ("2024-01-04", 120.0)],
    )
    engine_conn.commit()

    with pytest.raises(ValueError, match="Market data coverage is insufficient"):
        BacktestEngine(engine_conn).run(
            BacktestConfig(
                start_date=date(2024, 1, 2),
                end_date=date(2024, 1, 4),
                initial_capital=100_000,
                rebalance_frequency="monthly",
                target_weights={"해외주식": 1.0},
            )
        )
