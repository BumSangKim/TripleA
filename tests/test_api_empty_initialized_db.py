import sqlite3

from fastapi.testclient import TestClient

from api.db.initialize import initialize_database
from api.main import app


def test_empty_initialized_db_supports_macro_and_system_ui_endpoints(tmp_path, monkeypatch):
    db_path = str(tmp_path / "ui_empty.db")
    monkeypatch.setattr("api.db.connection.DB_PATH", db_path)
    initialize_database()

    conn = sqlite3.connect(db_path)
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    conn.close()

    assert "indicators" in tables

    with TestClient(app) as client:
        macro_response = client.get("/api/macro/summary")
        system_response = client.get("/api/system/status")

    assert macro_response.status_code == 200
    assert macro_response.json() == []
    assert system_response.status_code == 200
    assert system_response.json()["pipeline_status"] == "미확인"
