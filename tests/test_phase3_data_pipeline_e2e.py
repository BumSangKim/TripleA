import os
import sqlite3
from datetime import date

from fastapi.testclient import TestClient

from api.data.ingestion import check_current_quotes, collect_price_history
from api.data.repository import read_historical_prices
from api.data.snapshot import build_data_snapshot
from api.data.source_registry import load_data_sources


def test_phase3_mock_data_pipeline_e2e(tmp_path, monkeypatch):
    db_path = str(tmp_path / "phase3_e2e.db")
    os.environ["DB_PATH"] = db_path

    from api import db as api_db
    from api.main import app

    monkeypatch.setattr(api_db, "DB_PATH", db_path)
    api_db.ensure_dashboard_tables()

    sources = load_data_sources()
    price_source = [source for source in sources if source.source_id == "mock_krx_daily_prices"][0]
    quote_source = [source for source in sources if source.source_id == "mock_current_quotes"][0]

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    price_result = collect_price_history(
        source=price_source,
        start_date=date(2026, 5, 26),
        end_date=date(2026, 5, 27),
        db_session=conn,
    )
    quote_result = check_current_quotes(source=quote_source, db_session=conn)
    snapshot = build_data_snapshot(
        conn=conn,
        as_of_date=date(2026, 5, 27),
        dataset_types=["market_price_daily"],
        symbols=[price_source.symbols_or_indicators[0]],
    )

    assert price_result.status == "success"
    assert quote_result.status == "success"
    assert snapshot.included_datasets["market_price_daily"]
    assert read_historical_prices(
        symbol=price_source.symbols_or_indicators[0],
        market="KRX",
        start_date="2026-05-26",
        end_date="2026-05-27",
        db_session=conn,
    )

    with TestClient(app) as client:
        response = client.get("/api/data/status")
        quotes = client.get(f"/api/data/quotes/latest?symbols={quote_source.symbols_or_indicators[0]}")

    assert response.status_code == 200
    assert response.json()["datasets"]
    assert quotes.status_code == 200
    assert quotes.json()["quotes"][0]["status"] == "ok"

    del os.environ["DB_PATH"]
