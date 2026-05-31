from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Mapping

from api.features.capex_cycle.models import (
    CapexDecisionAuditRow,
    CapexScenarioSnapshot,
    CapexScoreSnapshot,
    CapexValuationSnapshot,
)


class CapexCycleSnapshotRepository:
    def __init__(
        self,
        *,
        score_snapshots: Iterable[CapexScoreSnapshot] | None = None,
        scenario_snapshots: Iterable[CapexScenarioSnapshot] | None = None,
        valuation_snapshots: Iterable[CapexValuationSnapshot] | None = None,
        audit_rows: Iterable[CapexDecisionAuditRow] | None = None,
        universe_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self._score_snapshots = tuple(score_snapshots or ())
        self._scenario_snapshots = tuple(scenario_snapshots or ())
        self._valuation_snapshots = tuple(valuation_snapshots or ())
        self._audit_rows = tuple(audit_rows or ())
        self._universe_metadata = dict(universe_metadata or {})

    def get_latest_score_snapshot(
        self,
        *,
        as_of_date: date | None = None,
        asset_id: str | None = None,
        score_type: str | None = None,
    ) -> CapexScoreSnapshot | None:
        rows = [
            row
            for row in self._score_snapshots
            if _as_of_filter(row.as_of_date, as_of_date)
            and (asset_id is None or row.entity_id == asset_id)
            and (score_type is None or row.score_type == score_type)
        ]
        return _latest(rows)

    def get_latest_scenario_snapshot(self, *, as_of_date: date | None = None) -> CapexScenarioSnapshot | None:
        return _latest([row for row in self._scenario_snapshots if _as_of_filter(row.as_of_date, as_of_date)])

    def get_latest_valuation_snapshot(
        self,
        *,
        asset_id: str,
        as_of_date: date | None = None,
    ) -> CapexValuationSnapshot | None:
        rows = [
            row
            for row in self._valuation_snapshots
            if row.asset_id == asset_id and _as_of_filter(row.as_of_date, as_of_date)
        ]
        return _latest(rows)

    def get_audit_rows(self, *, snapshot_id: str | None = None, limit: int = 100) -> list[CapexDecisionAuditRow]:
        rows = [row for row in self._audit_rows if snapshot_id is None or row.snapshot_id == snapshot_id]
        rows = sorted(rows, key=lambda row: (row.as_of_date, row.audit_id), reverse=True)
        return rows[: max(0, int(limit))]

    def get_universe_metadata(self, *, as_of_date: date | None = None) -> Mapping[str, Any]:
        metadata = dict(self._universe_metadata)
        if as_of_date is not None:
            metadata.setdefault("as_of_date", as_of_date.isoformat())
        return metadata


def _as_of_filter(row_date: date, as_of_date: date | None) -> bool:
    return as_of_date is None or row_date <= as_of_date


def _latest(rows):
    if not rows:
        return None
    return sorted(rows, key=lambda row: (row.as_of_date, row.snapshot_id))[-1]
