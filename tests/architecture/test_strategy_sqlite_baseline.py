from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STRATEGY_ROOT = ROOT / "api" / "strategy"
SQLITE_IMPORT_BASELINE = {
    "api/strategy/common_sector_scoring_engine.py",
    "api/strategy/decision_logger.py",
    "api/strategy/macro_engine.py",
    "api/strategy/score_layer.py",
    "api/strategy/score_store_service.py",
    "api/strategy/triplea_allocator.py",
}


def test_strategy_sqlite_imports_match_current_baseline():
    current = {
        str(path.relative_to(ROOT))
        for path in STRATEGY_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts and _imports_sqlite(path)
    }

    assert current == SQLITE_IMPORT_BASELINE, (
        "api/strategy sqlite import baseline changed. "
        "If a file was removed from sqlite usage, shrink SQLITE_IMPORT_BASELINE; "
        "if a file was added, introduce a port/repository boundary instead."
    )


def _imports_sqlite(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == "sqlite3" for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module == "sqlite3":
                return True
    return False
