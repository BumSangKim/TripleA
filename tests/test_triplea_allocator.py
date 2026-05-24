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
