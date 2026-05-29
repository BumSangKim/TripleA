from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.features.backtests.router import router


def _build_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_paths_preserved():
    paths = {r.path for r in _build_client().app.routes}
    assert "/api/backtests/run" in paths
    assert "/api/backtests/runs" in paths
    assert "/api/backtests/runs/{run_id}" in paths
    assert "/api/backtests/runs/{run_id}/decisions" in paths
    assert "/api/backtests/runs/{run_id}/positions" in paths
    assert "/api/backtests/runs/{run_id}/trades" in paths


def test_no_db_import():
    from pathlib import Path
    assert "from api.db" not in Path("api/features/backtests/router.py").read_text()
