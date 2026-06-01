from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

from api.domain.strategy_inputs import (
    BottleneckIndicatorInput,
    BottleneckSnapshotInput,
    MacroIndicatorInput,
    MacroSnapshotInput,
    PriceHistoryPointInput,
)


def test_macro_snapshot_get_value_allows_case_insensitive_keys():
    snapshot = MacroSnapshotInput(
        as_of_date=date(2024, 3, 10),
        indicators={
            "vixcls": MacroIndicatorInput(
                indicator="vixcls",
                value=18.5,
                unit=None,
                data_date=date(2024, 3, 8),
                source="fixture",
            ),
        },
    )

    assert snapshot.get_value("VIXCLS") == 18.5
    assert snapshot.get_value("missing", "VIXCLS") == 18.5


def test_empty_macro_snapshot_returns_none():
    snapshot = MacroSnapshotInput(as_of_date=date(2024, 3, 10))

    assert snapshot.get_value("VIXCLS") is None


def test_bottleneck_snapshot_preserves_indicator_list():
    indicator = BottleneckIndicatorInput(
        indicator_key="RS_SEMI",
        indicator_name="Relative strength",
        sector_code="SEMICONDUCTOR",
        value_date=date(2024, 3, 1),
        release_date=date(2024, 3, 5),
        value=72.0,
        unit="score",
        source="fixture",
        layer="relative_strength",
    )
    snapshot = BottleneckSnapshotInput(
        as_of_date=date(2024, 3, 10),
        lookback_months=12,
        indicators=[indicator],
    )

    assert snapshot.indicators == [indicator]


def test_price_history_point_preserves_asset_and_date_fields():
    point = PriceHistoryPointInput(
        asset_code="SMH",
        price_date=date(2024, 3, 8),
        price=225.25,
    )

    assert point.asset_code == "SMH"
    assert point.price_date == date(2024, 3, 8)
    assert point.price == 225.25


def test_strategy_input_domain_module_stays_pure():
    path = Path("api/domain/strategy_inputs.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_modules = {"fastapi", "starlette", "sqlite3", "api.db", "api.features"}

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert imports.isdisjoint(forbidden_modules)

