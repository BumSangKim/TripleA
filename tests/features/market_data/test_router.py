from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.features.market_data.router import router


def _build_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_paths_preserved():
    paths = {r.path for r in _build_client().app.routes}
    assert "/api/market-data/assets" in paths
    assert "/api/market-data/coverage" in paths


def test_no_db_import():
    from pathlib import Path
    src = Path("api/features/market_data/router.py").read_text()
    assert "from api.db" not in src
    assert "from .repository" not in src
