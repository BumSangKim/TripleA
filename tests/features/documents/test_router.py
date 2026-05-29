from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.features.documents.router import router


def _build_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_paths_preserved():
    paths = {r.path for r in _build_client().app.routes}
    assert "/api/documents" in paths
    assert "/api/documents/counts" in paths
    assert "/api/documents/{doc_id}" in paths


def test_no_db_import():
    from pathlib import Path
    src = Path("api/features/documents/router.py").read_text()
    assert "from api.db" not in src
    assert "from .repository" not in src
