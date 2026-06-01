from __future__ import annotations

from datetime import date
from typing import Any, Protocol, runtime_checkable

from api.domain.strategy_inputs import (
    BottleneckSnapshotInput,
    MacroSnapshotInput,
    PriceHistoryPointInput,
    SectorAssetMappingInput,
    StrategyDecisionLogInput,
)


# Trade snapshot input already has a dedicated port in api.strategy.trade_data_ports.


@runtime_checkable
class MacroSnapshotReader(Protocol):
    def read_macro_snapshot(self, as_of_date: date) -> MacroSnapshotInput:
        ...


@runtime_checkable
class BottleneckSnapshotReader(Protocol):
    def read_bottleneck_snapshot(
        self,
        as_of_date: date,
        *,
        lookback_months: int,
    ) -> BottleneckSnapshotInput:
        ...


@runtime_checkable
class SectorAssetMappingReader(Protocol):
    def read_sector_asset_mappings(self) -> dict[str, list[SectorAssetMappingInput]]:
        ...


@runtime_checkable
class PriceHistoryReader(Protocol):
    def read_price_history(
        self,
        asset_code: str,
        *,
        start_date: date,
        end_date: date,
    ) -> list[PriceHistoryPointInput]:
        ...


@runtime_checkable
class StrategyDecisionLogWriter(Protocol):
    def write_decision_log(self, payload: StrategyDecisionLogInput) -> None:
        ...


@runtime_checkable
class StrategyScoreStore(Protocol):
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
        ...

    def insert_value(self, run_id: str, output: Any) -> None:
        ...

    def lookup_previous_score(
        self,
        score_key: str,
        subject_type: str,
        subject_id: str,
        before_date: date,
    ) -> float | None:
        ...

    def values_for_run(self, run_id: str) -> list[dict[str, Any]]:
        ...

