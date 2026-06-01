from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

from api.domain.strategy_inputs import BottleneckSnapshotInput
from api.strategy.bottleneck_sector_engine import BottleneckSectorEngine


class EmptyBottleneckReader:
    def read_bottleneck_snapshot(
        self,
        as_of_date: date,
        *,
        lookback_months: int,
    ) -> BottleneckSnapshotInput:
        return BottleneckSnapshotInput(as_of_date=as_of_date, lookback_months=lookback_months)


def test_bottleneck_sector_engine_has_no_root_service_or_db_imports():
    path = Path("api/strategy/bottleneck_sector_engine.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = {
        "api." + "bottleneck" + "_data_service",
        "sqlite3",
        "api.db",
        "api.features",
    }

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert imports.isdisjoint(forbidden)


def test_bottleneck_sector_engine_empty_reader_stays_neutral_safe():
    scores = {
        score.sector_code: score
        for score in BottleneckSectorEngine(
            bottleneck_snapshot_reader=EmptyBottleneckReader()
        ).score(date(2024, 3, 10), lookback_months=12)
    }

    assert scores["SEMICONDUCTOR"].total_score == 50.0
    assert scores["SEMICONDUCTOR"].regime == "inactive"
