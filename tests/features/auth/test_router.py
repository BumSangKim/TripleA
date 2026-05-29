from __future__ import annotations

from fastapi.testclient import TestClient

from api.features.auth.router import router
from fastapi import FastAPI


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_login_valid_credentials():
    client = _build_client()
    res = client.post("/api/auth/token", data={"username": "admin", "password": "triplea123"})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_invalid_credentials():
    client = _build_client()
    res = client.post("/api/auth/token", data={"username": "admin", "password": "wrong"})
    assert res.status_code == 401


def test_auth_path_preserved():
    client = _build_client()
    paths = {r.path for r in client.app.routes}
    assert "/api/auth/token" in paths


def test_router_no_db_import():
    import ast
    from pathlib import Path

    src = Path("api/features/auth/router.py").read_text()
    assert "from api.db" not in src
    assert "import api.db" not in src


def test_router_no_repository_import():
    from pathlib import Path

    src = Path("api/features/auth/router.py").read_text()
    tree = __import__("ast").parse(src)
    imports = []
    for node in __import__("ast").walk(tree):
        if isinstance(node, __import__("ast").ImportFrom) and node.module:
            imports.append(node.module)
    repo_imports = [i for i in imports if i.endswith(".repository")]
    assert not repo_imports
