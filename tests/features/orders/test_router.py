from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.features.orders.router import router


def _build_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_paths_preserved():
    paths = {r.path for r in _build_client().app.routes}
    assert "/api/orders/drafts" in paths
    assert "/api/orders/draft" in paths
    assert "/api/orders/execute" in paths


def test_no_db_import():
    from pathlib import Path
    assert "from api.db" not in Path("api/features/orders/router.py").read_text()


def test_no_repository_import():
    import ast
    from pathlib import Path
    src = Path("api/features/orders/router.py").read_text()
    imports = [n.module for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ImportFrom) and n.module]
    assert not [i for i in imports if i.endswith(".repository")]
