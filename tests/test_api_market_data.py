import os
import sqlite3

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def md_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "market_data.db")
    os.environ["DB_PATH"] = db_path

    import api.db.connection as api_db
    from api.db.initialize import initialize_database
    from api.main import app

    monkeypatch.setattr(api_db, "DB_PATH", db_path)
    initialize_database()

    with TestClient(app) as client:
        yield client, db_path

    del os.environ["DB_PATH"]


def _seed_prices(db_path: str, rows: list[tuple]) -> None:
    """rows: (asset_code, price_date, close, currency)"""
    conn = sqlite3.connect(db_path)
    conn.executemany(
        """
        INSERT OR REPLACE INTO market_prices (asset_code, price_date, close, currency, source)
        VALUES (?, ?, ?, ?, 'test')
        """,
        rows,
    )
    conn.commit()
    conn.close()


def _seed_fx(db_path: str, rows: list[tuple]) -> None:
    """rows: (rate_date, rate)  — always USD/KRW"""
    conn = sqlite3.connect(db_path)
    conn.executemany(
        """
        INSERT OR REPLACE INTO fx_rates (base_currency, quote_currency, rate_date, rate, source)
        VALUES ('USD', 'KRW', ?, ?, 'test')
        """,
        rows,
    )
    conn.commit()
    conn.close()


# ── /api/market-data/assets ──────────────────────────────────────────

def test_assets_returns_seeded_universe(md_client):
    client, _ = md_client
    resp = client.get("/api/market-data/assets")
    assert resp.status_code == 200
    data = resp.json()
    # ensure_dashboard_tables seeds at least some active assets
    assert isinstance(data, list)
    assert len(data) > 0
    first = data[0]
    assert "assetCode" in first
    assert "assetClass" in first
    assert "currency" in first
    assert "isActive" in first


def test_assets_active_only_default(md_client):
    client, _ = md_client
    resp = client.get("/api/market-data/assets")
    assert resp.status_code == 200
    for item in resp.json():
        assert item["isActive"] is True


def test_assets_include_inactive(md_client):
    client, _ = md_client
    resp = client.get("/api/market-data/assets?active_only=false")
    assert resp.status_code == 200
    # should still return all seeded rows (all happen to be active in seed)
    assert len(resp.json()) > 0


# ── /api/market-data/coverage ────────────────────────────────────────

def test_coverage_empty_db(md_client):
    client, _ = md_client
    resp = client.get("/api/market-data/coverage?start_date=2020-01-01&end_date=2020-12-31")
    assert resp.status_code == 200
    data = resp.json()
    assert "ok" in data
    assert "assets" in data
    assert "fxRates" in data
    assert "missingMessages" in data
    # no price data → not ok
    assert data["ok"] is False


def test_coverage_with_full_data(md_client):
    client, db_path = md_client
    # get the actual asset codes from the universe
    assets_resp = client.get("/api/market-data/assets")
    codes = {item["assetCode"]: item["currency"] for item in assets_resp.json()}

    krw_codes = [code for code, cur in codes.items() if cur == "KRW" or code == "CASH_KRW"]
    usd_codes = [code for code, cur in codes.items() if cur == "USD"]

    price_rows = []
    for code in codes:
        if code == "CASH_KRW":
            continue
        cur = codes[code]
        price_rows += [
            (code, "2022-01-03", 100.0, cur),
            (code, "2022-12-30", 110.0, cur),
        ]
    _seed_prices(db_path, price_rows)

    if usd_codes:
        _seed_fx(db_path, [("2022-01-03", 1200.0), ("2022-12-30", 1300.0)])

    resp = client.get("/api/market-data/coverage?start_date=2022-01-01&end_date=2022-12-31")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["assets"], list)
    assert isinstance(data["fxRates"], list)


def test_coverage_invalid_date_format(md_client):
    client, _ = md_client
    resp = client.get("/api/market-data/coverage?start_date=not-a-date&end_date=2022-12-31")
    assert resp.status_code == 422


def test_coverage_start_after_end(md_client):
    client, _ = md_client
    resp = client.get("/api/market-data/coverage?start_date=2022-12-31&end_date=2022-01-01")
    assert resp.status_code == 422


def test_coverage_asset_fields(md_client):
    client, db_path = md_client
    assets_resp = client.get("/api/market-data/assets")
    codes = {item["assetCode"]: item["currency"] for item in assets_resp.json()}
    price_rows = [
        (code, "2023-01-02", 100.0, cur)
        for code, cur in codes.items()
        if code != "CASH_KRW"
    ]
    _seed_prices(db_path, price_rows)
    _seed_fx(db_path, [("2023-01-02", 1300.0)])

    resp = client.get("/api/market-data/coverage?start_date=2023-01-01&end_date=2023-12-31")
    assert resp.status_code == 200
    data = resp.json()
    for item in data["assets"]:
        assert "assetCode" in item
        assert "currency" in item
        assert "pricePoints" in item
        assert "ok" in item
    for item in data["fxRates"]:
        assert "baseCurrency" in item
        assert "quoteCurrency" in item
        assert "ratePoints" in item
        assert "ok" in item
