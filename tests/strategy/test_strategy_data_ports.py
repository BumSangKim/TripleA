from __future__ import annotations

import ast
from datetime import date
from pathlib import Path
from typing import Any

from api.domain.strategy_inputs import (
    BottleneckSnapshotInput,
    MacroSnapshotInput,
    PriceHistoryPointInput,
    SectorAssetMappingInput,
    StrategyDecisionLogInput,
)
from api.strategy.data_ports import (
    BottleneckSnapshotReader,
    MacroSnapshotReader,
    PriceHistoryReader,
    SectorAssetMappingReader,
    StrategyDecisionLogWriter,
    StrategyScoreStore,
)


class FakeMacroReader:
    def read_macro_snapshot(self, as_of_date: date) -> MacroSnapshotInput:
        return MacroSnapshotInput(as_of_date=as_of_date)


class FakeBottleneckReader:
    def read_bottleneck_snapshot(
        self,
        as_of_date: date,
        *,
        lookback_months: int,
    ) -> BottleneckSnapshotInput:
        return BottleneckSnapshotInput(as_of_date=as_of_date, lookback_months=lookback_months)


class FakeMappingReader:
    def read_sector_asset_mappings(self) -> dict[str, list[SectorAssetMappingInput]]:
        return {}


class FakePriceReader:
    def read_price_history(
        self,
        asset_code: str,
        *,
        start_date: date,
        end_date: date,
    ) -> list[PriceHistoryPointInput]:
        return []


class FakeDecisionWriter:
    def write_decision_log(self, payload: StrategyDecisionLogInput) -> None:
        self.payload = payload


class FakeScoreStore:
    def create_run(
        self,
        run_id: str,
        feature_snapshot_id: str,
        as_of_date: date,
        event_profile: str,
        parameter_version: str,
        model_version: str,
        status: str,
        warnings: list[str],
    ) -> None:
        self.run_id = run_id

    def insert_value(self, run_id: str, output: Any) -> None:
        self.output = output

    def lookup_previous_score(
        self,
        score_key: str,
        subject_type: str,
        subject_id: str,
        before_date: date,
    ) -> float | None:
        return None

    def values_for_run(self, run_id: str) -> list[dict[str, Any]]:
        return []


def test_fake_classes_structurally_satisfy_strategy_data_ports():
    assert isinstance(FakeMacroReader(), MacroSnapshotReader)
    assert isinstance(FakeBottleneckReader(), BottleneckSnapshotReader)
    assert isinstance(FakeMappingReader(), SectorAssetMappingReader)
    assert isinstance(FakePriceReader(), PriceHistoryReader)
    assert isinstance(FakeDecisionWriter(), StrategyDecisionLogWriter)
    assert isinstance(FakeScoreStore(), StrategyScoreStore)


def test_port_method_names_match_decoupling_contract():
    assert hasattr(MacroSnapshotReader, "read_macro_snapshot")
    assert hasattr(BottleneckSnapshotReader, "read_bottleneck_snapshot")
    assert hasattr(SectorAssetMappingReader, "read_sector_asset_mappings")
    assert hasattr(PriceHistoryReader, "read_price_history")
    assert hasattr(StrategyDecisionLogWriter, "write_decision_log")
    assert hasattr(StrategyScoreStore, "lookup_previous_score")


def test_strategy_data_ports_do_not_import_forbidden_modules():
    path = Path("api/strategy/data_ports.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_modules = {"sqlite3", "api.db", "api.features", "fastapi", "starlette"}

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert imports.isdisjoint(forbidden_modules)

