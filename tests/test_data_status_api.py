import os
import sqlite3
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from api.data.models import CurrentQuote, DataQualityCheck
from api.data.repository import upsert_current_quote, upsert_quality_check


@pytest.fixture()
def data_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "data_status.db")
    os.environ["DB_PATH"] = db_path

    import api.db.connection as api_db
    from api.db.initialize import initialize_database
    from api.main import app

    monkeypatch.setattr(api_db, "DB_PATH", db_path)
    initialize_database()

    with TestClient(app) as client:
        yield client, db_path

    del os.environ["DB_PATH"]


def _seed_data_status(db_path: str, *, stale: bool = False):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    now = datetime(2026, 5, 27, tzinfo=UTC)
    upsert_quality_check(
        DataQualityCheck(
            dataset_key="market_price:mock_krx_daily_prices",
            source="mock",
            as_of_date=date(2026, 5, 27),
            quality_score=0.5 if stale else 1.0,
            missing_ratio=0.2 if stale else 0.0,
            is_stale=stale,
            warnings=["stale_data"] if stale else [],
            fallback_policy="use_conservative_fallback",
            updated_at=now,
        ),
        db_session=conn,
    )
    upsert_current_quote(
        CurrentQuote(
            symbol="360750",
            market="KRX",
            price=Decimal("10000"),
            currency="KRW",
            quote_time=now,
            source="mock",
            as_of_date=date(2026, 5, 27),
            updated_at=now,
        ),
        db_session=conn,
    )
    conn.close()


def test_data_status_schema_and_ok_response(data_client):
    client, db_path = data_client
    _seed_data_status(db_path)

    response = client.get("/api/data/status")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["datasets"][0]["datasetKey"] == "market_price:mock_krx_daily_prices"
    assert "qualityScore" in data["datasets"][0]


def test_data_status_degraded_response(data_client):
    client, db_path = data_client
    _seed_data_status(db_path, stale=True)

    response = client.get("/api/data/status")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


def test_data_status_missing_dataset_is_degraded_not_500(data_client):
    client, _ = data_client

    response = client.get("/api/data/status/missing:dataset")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert "dataset_not_found" in response.json()["warnings"]


def test_latest_quote_endpoint(data_client):
    client, db_path = data_client
    _seed_data_status(db_path)

    response = client.get("/api/data/quotes/latest?symbols=360750,NOPE")

    assert response.status_code == 200
    quotes = response.json()["quotes"]
    assert quotes[0]["status"] == "ok"
    assert quotes[1]["status"] == "missing"
