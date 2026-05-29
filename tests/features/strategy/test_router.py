from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.features.strategy.router import router


def _build_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_paths_preserved():
    paths = {r.path for r in _build_client().app.routes}
    assert "/api/strategy/universes" in paths
    assert "/api/strategy/profiles" in paths
    assert "/api/strategy/sector-taxonomy" in paths


def test_no_db_import():
    from pathlib import Path
    assert "from api.db" not in Path("api/features/strategy/router.py").read_text()
