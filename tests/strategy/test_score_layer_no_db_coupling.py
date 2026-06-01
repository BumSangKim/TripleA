from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

from api.strategy.score_layer import ScoreRunner


def test_score_layer_has_no_sqlite_or_score_store_repository_imports():
    path = Path("api/strategy/score_layer.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = {
        "sqlite3",
        "api.db",
        "api.score_pipeline.score_store",
    }

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert imports.isdisjoint(forbidden)


def test_score_runner_without_store_remains_pure_calculation_path():
    runner = ScoreRunner({}, {"normal": {"span_adjustments": {}}})

    summary, outputs = runner.run(
        as_of_date=date(2026, 5, 27),
        feature_snapshot_id="snap-1",
        feature_values={},
    )

    assert outputs == []
    assert summary.count_total == 0
    assert summary.status == "SUCCESS"
