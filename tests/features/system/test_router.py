from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.features.system.router import router


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_health_returns_ok():
    client = _build_client()
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_health_path_preserved():
    client = _build_client()
    paths = {r.path for r in client.app.routes}
    assert "/api/health" in paths


def test_system_status_path_preserved():
    client = _build_client()
    paths = {r.path for r in client.app.routes}
    assert "/api/system/status" in paths


def test_modes_path_preserved():
    client = _build_client()
    paths = {r.path for r in client.app.routes}
    assert "/api/modes" in paths


def test_router_no_db_import():
    from pathlib import Path

    src = Path("api/features/system/router.py").read_text()
    assert "from api.db" not in src
    assert "import api.db" not in src


def test_router_no_repository_import():
    import ast
    from pathlib import Path

    src = Path("api/features/system/router.py").read_text()
    tree = ast.parse(src)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    repo_imports = [i for i in imports if i.endswith(".repository")]
    assert not repo_imports
