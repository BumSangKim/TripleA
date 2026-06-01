import sqlite3
from datetime import date

from api.data.strategy_data_readers import SqliteBottleneckSnapshotReader
from api.db.initialize import initialize_database as ensure_dashboard_tables
from api.features.market_data.trade_data_service import SqliteTradeSnapshotReader
from api.strategy.bottleneck_sector_engine import BottleneckSectorEngine


def test_bottleneck_sector_engine_scores_semiconductor_from_trade_and_relative_strength(tmp_path, monkeypatch):
    db_path = str(tmp_path / "bottleneck_engine.db")
    monkeypatch.setattr("api.db.connection.DB_PATH", db_path)
    ensure_dashboard_tables()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        INSERT INTO trade_series
        (period, country, flow, item_code, amount_usd, yoy, source, release_date)
        VALUES ('2024-01', 'KR', 'export', 'HS_8542', 100, 30, 'test', '2024-02-15')
        """
    )
    conn.execute(
        """
        INSERT INTO bottleneck_indicators
        (indicator_key, sector_code, value_date, release_date, value, source, layer)
        VALUES ('RS_SMH_SPY', 'SEMICONDUCTOR', '2024-02-29', '2024-03-01', 85, 'test', 'relative_strength')
        """
    )

    scores = {
        score.sector_code: score
        for score in BottleneckSectorEngine(
            conn,
            bottleneck_snapshot_reader=SqliteBottleneckSnapshotReader(conn),
            trade_snapshot_reader=SqliteTradeSnapshotReader(conn),
        ).score(date(2024, 3, 10), lookback_months=12)
    }

    assert scores["SEMICONDUCTOR"].trade_score == 80.0
    assert scores["SEMICONDUCTOR"].relative_strength_score == 85.0
    assert scores["SEMICONDUCTOR"].regime == "active"


def test_bottleneck_sector_engine_ignores_future_release_rows(tmp_path, monkeypatch):
    db_path = str(tmp_path / "bottleneck_engine.db")
    monkeypatch.setattr("api.db.connection.DB_PATH", db_path)
    ensure_dashboard_tables()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executemany(
        """
        INSERT INTO trade_series
        (period, country, flow, item_code, amount_usd, yoy, source, release_date)
        VALUES (?, 'KR', 'export', 'HS_8542', 100, ?, 'test', ?)
        """,
        [
            ("2024-01", 5.0, "2024-02-15"),
            ("2024-02", 80.0, "2024-03-15"),
        ],
    )

    scores = {
        score.sector_code: score
        for score in BottleneckSectorEngine(
            conn,
            bottleneck_snapshot_reader=SqliteBottleneckSnapshotReader(conn),
            trade_snapshot_reader=SqliteTradeSnapshotReader(conn),
        ).score(date(2024, 3, 10), lookback_months=12)
    }

    assert scores["SEMICONDUCTOR"].trade_score == 55.0
    assert all("+80.0%" not in reason for reason in scores["SEMICONDUCTOR"].reasons)
