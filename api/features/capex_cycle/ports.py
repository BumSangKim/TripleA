from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Protocol, runtime_checkable

from api.features.capex_cycle.schemas import (
    BioCapexBottleneckScoreResponse,
    CapexCycleScoreResponse,
    CapexScenarioResponse,
    CapexValuationResponse,
)


CapexScoreSnapshot = CapexCycleScoreResponse | BioCapexBottleneckScoreResponse


@runtime_checkable
class ICapexCycleRepository(Protocol):
    def get_latest_score_snapshot(
        self,
        *,
        as_of_date: date | None = None,
        asset_id: str | None = None,
    ) -> CapexScoreSnapshot | None:
        ...

    def get_latest_scenario_snapshot(self, *, as_of_date: date | None = None) -> CapexScenarioResponse | None:
        ...

    def get_latest_valuation_snapshot(
        self,
        *,
        asset_id: str,
        as_of_date: date | None = None,
    ) -> CapexValuationResponse | None:
        ...

    def get_universe_metadata(self, *, as_of_date: date | None = None) -> Mapping[str, Any]:
        ...


@runtime_checkable
class ICapexCycleService(Protocol):
    def get_scores(self, *, as_of_date: date | None = None, asset_id: str | None = None) -> list[CapexScoreSnapshot]:
        ...

    def get_scenario(self, *, as_of_date: date | None = None) -> CapexScenarioResponse:
        ...

    def get_valuation(self, *, asset_id: str, as_of_date: date | None = None) -> CapexValuationResponse:
        ...
