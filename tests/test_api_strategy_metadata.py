import os

from fastapi.testclient import TestClient


def test_strategy_metadata_endpoints_return_config(tmp_path, monkeypatch):
    db_path = str(tmp_path / "strategy.db")
    os.environ["DB_PATH"] = db_path

    from api import db as api_db
    from api.main import app

    monkeypatch.setattr(api_db, "DB_PATH", db_path)
    api_db.ensure_dashboard_tables()

    with TestClient(app) as client:
        universes = client.get("/api/strategy/universes")
        profiles = client.get("/api/strategy/profiles")
        taxonomy = client.get("/api/strategy/sector-taxonomy")

    del os.environ["DB_PATH"]

    assert universes.status_code == 200
    assert profiles.status_code == 200
    assert taxonomy.status_code == 200
    assert "default_global" in universes.json()
    assert "balanced" in profiles.json()
    assert "SEMICONDUCTOR" in taxonomy.json()
