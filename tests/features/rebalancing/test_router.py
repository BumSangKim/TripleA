from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.features.rebalancing.router import router


def _build_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_paths_preserved():
    client = _build_client()
    paths = {r.path for r in client.app.routes}
    assert "/api/rebalancing/suggestions" in paths
    assert "/api/rebalancing/run" in paths
    assert "/api/rebalancing/results" in paths
    assert "/api/engine/risk-budget" in paths


def test_no_db_import():
    from pathlib import Path
    src = Path("api/features/rebalancing/router.py").read_text()
    assert "from api.db" not in src


def test_no_repository_import():
    import ast
    from pathlib import Path
    src = Path("api/features/rebalancing/router.py").read_text()
    tree = ast.parse(src)
    imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]
    assert not [i for i in imports if i.endswith(".repository")]
