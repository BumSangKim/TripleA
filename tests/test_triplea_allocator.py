import sqlite3
from datetime import date

from api.strategy.triplea_allocator import TripleAAllocator


def test_triplea_allocator_uses_risk_profile_bucket_targets():
    conn = sqlite3.connect(":memory:")
    decision = TripleAAllocator(
        conn,
        risk_profile="balanced",
        universe_id="default_global",
    ).allocate(date(2024, 1, 31))

    assert round(sum(decision.final_weights.values()), 6) == 1.0
    assert round(decision.bucket_weights["AGGRESSIVE_ALPHA"], 6) == 0.45
    assert round(decision.bucket_weights["DEFENSIVE_CORE"], 6) == 0.40
    assert round(decision.bucket_weights["LIQUIDITY"], 6) == 0.15
    assert "SMH" not in decision.final_weights
    assert decision.final_weights["CASH_KRW"] == 0.15
    assert decision.macro_regime == "neutral"
    assert decision.reasons


def test_triplea_allocator_changes_weights_by_risk_profile():
    conn = sqlite3.connect(":memory:")
    aggressive = TripleAAllocator(conn, risk_profile="aggressive").allocate(date(2024, 1, 31))
    defensive = TripleAAllocator(conn, risk_profile="defensive").allocate(date(2024, 1, 31))

    assert aggressive.bucket_weights["AGGRESSIVE_ALPHA"] > defensive.bucket_weights["AGGRESSIVE_ALPHA"]
    assert defensive.bucket_weights["DEFENSIVE_CORE"] > aggressive.bucket_weights["DEFENSIVE_CORE"]


def test_triplea_allocator_applies_active_bottleneck_sector_tilt(tmp_path, monkeypatch):
    from api.db import ensure_dashboard_tables

    db_path = str(tmp_path / "allocator.db")
    monkeypatch.setattr("api.db.DB_PATH", db_path)
    ensure_dashboard_tables()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        INSERT INTO trade_series
        (period, country, flow, item_code, amount_usd, yoy, source, release_date)
        VALUES ('2024-01', 'KR', 'export', 'HS_8542', 100, 35, 'test', '2024-02-15')
        """
    )
    conn.execute(
        """
        INSERT INTO bottleneck_indicators
        (indicator_key, sector_code, value_date, release_date, value, source, layer)
        VALUES ('RS_SMH_SPY', 'SEMICONDUCTOR', '2024-02-29', '2024-03-01', 90, 'test', 'relative_strength')
        """
    )

    decision = TripleAAllocator(conn, risk_profile="balanced").allocate(date(2024, 3, 10))

    assert decision.final_weights["SMH"] > 0
    assert decision.bottleneck_scores["SEMICONDUCTOR"] >= 70
    assert any("SEMICONDUCTOR active tilt" in reason for reason in decision.reasons)
