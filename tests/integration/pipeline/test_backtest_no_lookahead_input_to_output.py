from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from api.backtest_engine import BacktestConfig, BacktestEngine
from api.db.initialize import initialize_database
from api.strategy.types import AllocationDecision


class ReadOnlySpyAllocator:
    def asset_codes(self) -> list[str]:
        return ["SPY"]

    def allocate(
        self,
        as_of_date: date,
        *,
        previous_weights: dict[str, float] | None = None,
    ) -> AllocationDecision:
        return AllocationDecision(
            as_of_date=as_of_date,
            strategy_mode="triplea_dynamic",
            risk_profile="balanced",
            universe_id="test",
            macro_regime="neutral",
            macro_score=50,
            bucket_weights={"AGGRESSIVE_ALPHA": 1.0},
            final_weights={"SPY": 1.0},
            reasons=["fixture allocator: read-only no live execution"],
        )


@pytest.fixture()
def backtest_conn(tmp_path, monkeypatch):
    db_path = str(tmp_path / "backtest_no_lookahead.db")
    monkeypatch.setattr("api.db.connection.DB_PATH", db_path)
    initialize_database()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def test_backtest_no_lookahead_input_to_output_uses_prior_price_and_no_live_execution(backtest_conn):
    _insert_price(backtest_conn, "2024-01-01", 100.0)
    _insert_price(backtest_conn, "2024-01-03", 110.0)
    _insert_fx(backtest_conn, "2024-01-01", 1000.0)
    _insert_fx(backtest_conn, "2024-01-03", 1000.0)
    backtest_conn.commit()

    result = BacktestEngine(backtest_conn, allocator=ReadOnlySpyAllocator()).run(
        BacktestConfig(
            start_date=date(2024, 1, 2),
            end_date=date(2024, 1, 3),
            initial_capital=100_000,
            rebalance_frequency="monthly",
        )
    )

    assert [point.point_date for point in result.points] == [date(2024, 1, 2), date(2024, 1, 3)]
    assert [point.portfolio_value for point in result.points] == [100_000, 110_000]
    assert result.positions[0].point_date == date(2024, 1, 2)
    assert result.positions[0].price == 100.0
    assert result.positions[-1].point_date == date(2024, 1, 3)
    assert result.positions[-1].price == 110.0
    assert [trade.reason for trade in result.trades] == ["INITIAL_ALLOCATE"]
    assert result.decisions[0].reasons == ["fixture allocator: read-only no live execution"]


def test_backtest_no_lookahead_rejects_future_price_only(backtest_conn):
    _insert_price(backtest_conn, "2024-01-03", 110.0)
    _insert_fx(backtest_conn, "2024-01-01", 1000.0)
    _insert_fx(backtest_conn, "2024-01-03", 1000.0)
    backtest_conn.commit()

    with pytest.raises(ValueError, match="SPY: price data is missing"):
        BacktestEngine(backtest_conn, allocator=ReadOnlySpyAllocator()).run(
            BacktestConfig(
                start_date=date(2024, 1, 2),
                end_date=date(2024, 1, 3),
                initial_capital=100_000,
                rebalance_frequency="monthly",
            )
        )


def test_backtest_no_lookahead_rejects_future_fx_only(backtest_conn):
    _insert_price(backtest_conn, "2024-01-01", 100.0)
    _insert_price(backtest_conn, "2024-01-03", 110.0)
    _insert_fx(backtest_conn, "2024-01-03", 1000.0)
    backtest_conn.commit()

    with pytest.raises(ValueError, match="USD/KRW: FX data is missing"):
        BacktestEngine(backtest_conn, allocator=ReadOnlySpyAllocator()).run(
            BacktestConfig(
                start_date=date(2024, 1, 2),
                end_date=date(2024, 1, 3),
                initial_capital=100_000,
                rebalance_frequency="monthly",
            )
        )


def _insert_price(conn: sqlite3.Connection, price_date: str, close: float) -> None:
    conn.execute(
        """
        INSERT INTO market_prices
        (asset_code, price_date, close, currency, source)
        VALUES ('SPY', ?, ?, 'USD', 'test')
        """,
        (price_date, close),
    )


def _insert_fx(conn: sqlite3.Connection, rate_date: str, rate: float) -> None:
    conn.execute(
        """
        INSERT INTO fx_rates
        (base_currency, quote_currency, rate_date, rate, source)
        VALUES ('USD', 'KRW', ?, ?, 'test')
        """,
        (rate_date, rate),
    )
