from __future__ import annotations

import ast
from pathlib import Path


def test_decision_logger_has_no_db_reporting_or_feature_imports():
    path = Path("api/strategy/decision_logger.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = {
        "sqlite3",
        "api.db",
        "api.reporting",
        "api.features",
    }

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert imports.isdisjoint(forbidden)

