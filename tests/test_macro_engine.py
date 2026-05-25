import sqlite3
from datetime import date

from api.strategy.macro_engine import MacroEngine


def _macro_conn(rows: list[tuple]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE indicators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            indicator TEXT,
            value REAL,
            unit TEXT,
            date TEXT,
            source TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO indicators (indicator, value, unit, date, source) VALUES (?, ?, ?, ?, 'test')",
        rows,
    )
    return conn


def test_macro_engine_marks_high_vix_as_risk_off():
    conn = _macro_conn([
        ("VIXCLS", 38.0, "pt", "2024-01-02"),
        ("ISM_PMI", 44.0, "pt", "2024-01-02"),
    ])

    decision = MacroEngine(conn).evaluate(date(2024, 1, 3))

    assert decision.regime == "risk_off"
    assert decision.score <= 25
    assert any("VIX" in reason for reason in decision.reasons)


def test_macro_engine_ignores_future_indicator_rows():
    conn = _macro_conn([
        ("VIXCLS", 15.0, "pt", "2024-01-02"),
        ("VIXCLS", 40.0, "pt", "2024-01-10"),
    ])

    decision = MacroEngine(conn).evaluate(date(2024, 1, 5))

    assert decision.regime in {"neutral", "risk_on"}
    assert decision.indicators["VIXCLS"] == 15.0


def test_allocator_reduces_aggressive_bucket_in_risk_off_macro():
    conn = _macro_conn([
        ("VIXCLS", 40.0, "pt", "2024-01-02"),
        ("ISM_PMI", 44.0, "pt", "2024-01-02"),
    ])

    from api.strategy.triplea_allocator import TripleAAllocator

    decision = TripleAAllocator(conn, risk_profile="balanced").allocate(date(2024, 1, 3))

    assert decision.macro_regime == "risk_off"
    assert decision.bucket_weights["AGGRESSIVE_ALPHA"] < 0.45
    assert decision.bucket_weights["LIQUIDITY"] > 0.15
