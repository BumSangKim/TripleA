import sqlite3
from datetime import date

from api.data.strategy_data_readers import SqlitePriceHistoryReader
from api.strategy.common_sector_scoring_engine import CommonSectorScoringEngine


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE market_prices (asset_code TEXT, price_date TEXT, close REAL, adj_close REAL)")
    return conn


def test_common_sector_score_responds_to_relative_strength_and_missing_data():
    conn = _conn()
    conn.executemany("INSERT INTO market_prices VALUES (?, ?, ?, NULL)", [
        ("SMH", "2026-05-01", 100), ("SMH", "2026-05-27", 120),
        ("SPY", "2026-05-01", 100), ("SPY", "2026-05-27", 105),
    ])
    reader = SqlitePriceHistoryReader(conn)
    score = CommonSectorScoringEngine(reader).score_sector("SEMICONDUCTOR", "SMH", "SPY", date(2026, 5, 27))
    missing = CommonSectorScoringEngine(reader).score_sector("UNKNOWN", None, "SPY", date(2026, 5, 27))
    assert score.relative_strength_score > 0.5
    assert score.valuation_burden_score is None
    assert score.confidence < 0.75
    assert 0 <= score.total_common_score <= 1
    assert missing.confidence < score.confidence
