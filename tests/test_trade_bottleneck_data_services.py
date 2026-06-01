import sqlite3
from datetime import date

from api.data.bottleneck_snapshot_reader import get_bottleneck_snapshot, get_sector_asset_mappings
from api.db.initialize import initialize_database as ensure_dashboard_tables
from api.features.market_data.trade_data_service import get_trade_snapshot


def test_trade_snapshot_filters_by_release_date(tmp_path, monkeypatch):
    db_path = str(tmp_path / "trade.db")
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
            ("2024-01", 12.0, "2024-02-15"),
            ("2024-02", 30.0, "2024-03-15"),
        ],
    )

    snapshot = get_trade_snapshot(conn, date(2024, 3, 10), lookback_months=12)

    assert [item.period for item in snapshot.items] == ["2024-01"]
    assert snapshot.items[0].yoy == 12.0


def test_bottleneck_snapshot_filters_by_release_date_and_loads_sector_assets(tmp_path, monkeypatch):
    db_path = str(tmp_path / "bottleneck.db")
    monkeypatch.setattr("api.db.connection.DB_PATH", db_path)
    ensure_dashboard_tables()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executemany(
        """
        INSERT INTO bottleneck_indicators
        (indicator_key, sector_code, value_date, release_date, value, source, layer)
        VALUES ('RS_SMH_SPY', 'SEMICONDUCTOR', ?, ?, ?, 'test', 'relative_strength')
        """,
        [
            ("2024-02-29", "2024-03-01", 75.0),
            ("2024-03-31", "2024-04-01", 90.0),
        ],
    )

    snapshot = get_bottleneck_snapshot(conn, date(2024, 3, 10), lookback_months=12)
    mappings = get_sector_asset_mappings(conn)

    assert [item.value_date for item in snapshot.indicators] == [date(2024, 2, 29)]
    semiconductor_assets = {item.asset_code for item in mappings["SEMICONDUCTOR"]}
    assert {"000660", "SMH"} <= semiconductor_assets
