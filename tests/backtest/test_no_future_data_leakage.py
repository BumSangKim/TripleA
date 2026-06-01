from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

import pytest

from api.backtest_engine import BacktestConfig, BacktestEngine
from api.db.initialize import initialize_database
from api.strategy.types import AllocationDecision


@dataclass
class SignalReading:
    signal_date: date
    available_at: date
    label: str


class PointInTimeSignalAllocator:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def asset_codes(self) -> list[str]:
        return ["SPY"]

    def allocate(
        self,
        as_of_date: date,
        *,
        previous_weights: dict[str, float] | None = None,
    ) -> AllocationDecision:
        signal = _latest_available_signal(self.conn, as_of_date)
        if signal is None:
            reasons = ["REVIEW_REQUIRED_MISSING_SIGNAL"]
            macro_regime = "neutral"
            macro_score = 50
        else:
            reasons = [f"SIGNAL:{signal.label}", f"AVAILABLE_AT:{signal.available_at.isoformat()}"]
            macro_regime = "risk_off" if signal.label == "CURRENT_DEFENSIVE" else "risk_on"
            macro_score = 35 if signal.label == "CURRENT_DEFENSIVE" else 90
        return AllocationDecision(
            as_of_date=as_of_date,
            strategy_mode="simplified_backtest_fixture",
            risk_profile="balanced",
            universe_id="leakage_guard",
            macro_regime=macro_regime,
            macro_score=macro_score,
            bucket_weights={"AGGRESSIVE_ALPHA": 1.0},
            final_weights={"SPY": 1.0},
            reasons=reasons,
        )


@pytest.fixture()
def leakage_conn(tmp_path, monkeypatch):
    db_path = str(tmp_path / "backtest_leakage_guard.db")
    monkeypatch.setattr("api.db.connection.DB_PATH", db_path)
    initialize_database()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE fixture_signals (
            signal_date TEXT NOT NULL,
            available_at TEXT NOT NULL,
            label TEXT NOT NULL
        )
        """
    )
    yield conn
    conn.close()


def test_backtest_uses_only_price_fx_and_signal_available_on_decision_date(leakage_conn):
    _seed_prices_and_fx(leakage_conn)
    _seed_signals(leakage_conn)

    result = _run_backtest(leakage_conn)

    assert [point.point_date for point in result.points] == [date(2024, 1, 2), date(2024, 1, 3)]
    assert result.positions[0].point_date == date(2024, 1, 2)
    assert result.positions[0].price == 100.0
    assert result.positions[-1].point_date == date(2024, 1, 3)
    assert result.positions[-1].price == 200.0
    assert result.decisions[0].reasons == ["SIGNAL:CURRENT_DEFENSIVE", "AVAILABLE_AT:2024-01-01"]
    assert "FUTURE_RISK_ON" not in " ".join(result.decisions[0].reasons)
    assert result.total_return == pytest.approx(100.0)


def test_backtest_leakage_fixture_is_reproducible_with_fixed_inputs(leakage_conn):
    _seed_prices_and_fx(leakage_conn)
    _seed_signals(leakage_conn)

    first = _run_backtest(leakage_conn)
    second = _run_backtest(leakage_conn)

    assert first.points == second.points
    assert first.positions == second.positions
    assert first.trades == second.trades
    assert first.decisions == second.decisions


def test_backtest_cost_hooks_are_applied_without_live_execution(leakage_conn):
    _seed_prices_and_fx(leakage_conn)
    _seed_signals(leakage_conn)

    result = _run_backtest(leakage_conn, fee_bps=10.0, slippage_bps=5.0)

    assert result.trades
    assert result.trades[0].reason == "INITIAL_ALLOCATE"
    assert result.trades[0].fee > 0
    assert result.trades[0].slippage > 0
    assert result.trades[0].tax == 0
    assert not hasattr(result.trades[0], "broker_order_payload")


def test_missing_required_historical_price_fails_conservatively(leakage_conn):
    _insert_price(leakage_conn, "2024-01-03", 200.0)
    _insert_fx(leakage_conn, "2024-01-01", 1000.0)
    _insert_fx(leakage_conn, "2024-01-03", 1000.0)
    _seed_signals(leakage_conn)
    leakage_conn.commit()

    with pytest.raises(ValueError, match="SPY: price data is missing"):
        _run_backtest(leakage_conn)


def _run_backtest(conn: sqlite3.Connection, *, fee_bps: float = 0.0, slippage_bps: float = 0.0):
    return BacktestEngine(conn, allocator=PointInTimeSignalAllocator(conn)).run(
        BacktestConfig(
            start_date=date(2024, 1, 2),
            end_date=date(2024, 1, 3),
            initial_capital=100_000,
            rebalance_frequency="monthly",
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
        )
    )


def _seed_prices_and_fx(conn: sqlite3.Connection) -> None:
    _insert_price(conn, "2024-01-01", 100.0)
    _insert_price(conn, "2024-01-03", 200.0)
    _insert_fx(conn, "2024-01-01", 1000.0)
    _insert_fx(conn, "2024-01-03", 1000.0)
    conn.commit()


def _seed_signals(conn: sqlite3.Connection) -> None:
    conn.executemany(
        """
        INSERT INTO fixture_signals (signal_date, available_at, label)
        VALUES (?, ?, ?)
        """,
        [
            ("2024-01-01", "2024-01-01", "CURRENT_DEFENSIVE"),
            ("2024-01-03", "2024-01-03", "FUTURE_RISK_ON"),
        ],
    )
    conn.commit()


def _latest_available_signal(conn: sqlite3.Connection, as_of_date: date) -> SignalReading | None:
    row = conn.execute(
        """
        SELECT signal_date, available_at, label
        FROM fixture_signals
        WHERE signal_date <= ?
          AND available_at <= ?
        ORDER BY signal_date DESC, available_at DESC
        LIMIT 1
        """,
        (as_of_date.isoformat(), as_of_date.isoformat()),
    ).fetchone()
    if row is None:
        return None
    return SignalReading(date.fromisoformat(row["signal_date"]), date.fromisoformat(row["available_at"]), row["label"])


def _insert_price(conn: sqlite3.Connection, price_date: str, close: float) -> None:
    conn.execute(
        """
        INSERT INTO market_prices
        (asset_code, price_date, close, currency, source)
        VALUES ('SPY', ?, ?, 'USD', 'leakage_guard')
        """,
        (price_date, close),
    )


def _insert_fx(conn: sqlite3.Connection, rate_date: str, rate: float) -> None:
    conn.execute(
        """
        INSERT INTO fx_rates (base_currency, quote_currency, rate_date, rate, source)
        VALUES ('USD', 'KRW', ?, ?, 'leakage_guard')
        """,
        (rate_date, rate),
    )
