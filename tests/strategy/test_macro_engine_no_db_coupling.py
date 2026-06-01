from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

from api.domain.strategy_inputs import MacroIndicatorInput, MacroSnapshotInput
from api.strategy.macro_engine import MacroEngine


class FakeMacroReader:
    def read_macro_snapshot(self, as_of_date: date) -> MacroSnapshotInput:
        return MacroSnapshotInput(
            as_of_date=as_of_date,
            indicators={
                "VIXCLS": MacroIndicatorInput(
                    indicator="VIXCLS",
                    value=38.0,
                    unit="pt",
                    data_date=date(2024, 1, 2),
                    source="fake",
                ),
            },
        )


def test_macro_engine_has_no_db_or_root_macro_imports():
    path = Path("api/strategy/macro_engine.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = {"sqlite3", "api.macro_data_service", "api.db"}

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert imports.isdisjoint(forbidden)


def test_macro_engine_uses_fake_reader_for_deterministic_decision():
    decision = MacroEngine.from_reader(FakeMacroReader()).evaluate(date(2024, 1, 3))

    assert decision.regime == "risk_off"
    assert decision.indicators["VIXCLS"] == 38.0

