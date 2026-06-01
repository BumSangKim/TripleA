from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from api.backtest_engine import BacktestConfig, BacktestExecutionRunner
from api.db.initialize import initialize_database
from api.strategy.types import AllocationDecision


class SpyOnlyAllocator:
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
            reasons=["runner boundary fixture"],
        )


@pytest.fixture()
def runner_conn(tmp_path, monkeypatch):
    db_path = str(tmp_path / "runner_boundary.db")
    monkeypatch.setattr("api.db.connection.DB_PATH", db_path)
    initialize_database()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def test_backtest_execution_runner_returns_engine_result_without_live_execution(runner_conn):
    _seed_market_data(runner_conn)
    collector_calls: list[tuple[list[str], date, date]] = []

    def collector(conn: sqlite3.Connection, asset_codes: list[str], start: date, end: date) -> None:
        collector_calls.append((asset_codes, start, end))

    result = BacktestExecutionRunner(
        runner_conn,
        allocator=SpyOnlyAllocator(),
        market_data_collector=collector,
    ).run(_config())

    assert result.points
    assert result.trades[0].reason == "INITIAL_ALLOCATE"
    assert result.decisions[0].reasons == ["runner boundary fixture"]
    assert collector_calls == []


def test_backtest_execution_runner_uses_injected_collector_when_coverage_is_missing(runner_conn):
    collector_calls: list[tuple[list[str], date, date]] = []

    def collector(conn: sqlite3.Connection, asset_codes: list[str], start: date, end: date) -> None:
        collector_calls.append((asset_codes, start, end))
        _seed_market_data(conn)

    result = BacktestExecutionRunner(
        runner_conn,
        allocator=SpyOnlyAllocator(),
        market_data_collector=collector,
    ).run(_config())

    assert result.points[-1].portfolio_value == 110_000
    assert collector_calls == [(["SPY"], date(2024, 1, 2), date(2024, 1, 3))]


def test_backtest_execution_runner_fails_conservatively_when_coverage_remains_missing(runner_conn):
    collector_calls: list[list[str]] = []

    def collector(conn: sqlite3.Connection, asset_codes: list[str], start: date, end: date) -> None:
        collector_calls.append(asset_codes)

    with pytest.raises(ValueError, match="Market data coverage is insufficient"):
        BacktestExecutionRunner(
            runner_conn,
            allocator=SpyOnlyAllocator(),
            market_data_collector=collector,
        ).run(_config())

    assert collector_calls == [["SPY"]]


def _config() -> BacktestConfig:
    return BacktestConfig(
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 3),
        initial_capital=100_000,
        rebalance_frequency="monthly",
    )


def _seed_market_data(conn: sqlite3.Connection) -> None:
    conn.executemany(
        """
        INSERT OR REPLACE INTO market_prices
        (asset_code, price_date, close, currency, source)
        VALUES ('SPY', ?, ?, 'USD', 'test')
        """,
        [("2024-01-02", 100.0), ("2024-01-03", 110.0)],
    )
    conn.executemany(
        """
        INSERT OR REPLACE INTO fx_rates
        (base_currency, quote_currency, rate_date, rate, source)
        VALUES ('USD', 'KRW', ?, 1000.0, 'test')
        """,
        [("2024-01-02",), ("2024-01-03",)],
    )
    conn.commit()
