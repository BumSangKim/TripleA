from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Iterable, Sequence

from api.features.backtests.sector_component_models import (
    SectorComponentObservation,
    SectorComponentSnapshot,
    SectorComponentValidationWarning,
)
from api.plugin_boundary.time_guard import filter_available_values


def build_sector_component_snapshots(
    observations: Iterable[SectorComponentObservation],
    decision_dates: Sequence[date],
    *,
    required_components: Sequence[str],
    parameter_version: str,
    model_version: str,
    stale_after_days: int | None = None,
) -> tuple[SectorComponentSnapshot, ...]:
    rows = tuple(observations)
    sectors = sorted({row.sector_id for row in rows})
    snapshots: list[SectorComponentSnapshot] = []
    for decision_date in sorted(decision_dates):
        decision_time = _decision_time(decision_date)
        available_rows = filter_available_values(rows, decision_time)
        for sector_id in sectors:
            sector_rows = [row for row in available_rows if row.sector_id == sector_id]
            observations_for_snapshot = _latest_component_rows(sector_rows)
            available_at = max((row.available_at for row in observations_for_snapshot), default=decision_time)
            data_snapshot_id = _snapshot_id(sector_id, decision_date, parameter_version)
            warnings = tuple(
                _snapshot_warnings(
                    sector_id=sector_id,
                    decision_date=decision_date,
                    available_at=available_at,
                    data_snapshot_id=data_snapshot_id,
                    parameter_version=parameter_version,
                    model_version=model_version,
                    observations=observations_for_snapshot,
                    stale_after_days=stale_after_days,
                )
            )
            snapshots.append(
                SectorComponentSnapshot(
                    sector_id=sector_id,
                    as_of_date=decision_date,
                    available_at=available_at,
                    parameter_version=parameter_version,
                    model_version=model_version,
                    data_snapshot_id=data_snapshot_id,
                    observations=observations_for_snapshot,
                    required_components=tuple(required_components),
                    reason_codes=("SECTOR_COMPONENT_SNAPSHOT_BUILT",),
                    warnings=warnings,
                    fallback_state="HOLD" if warnings else "NO_ACTION",
                )
            )
    return tuple(snapshots)


def _latest_component_rows(rows: Sequence[SectorComponentObservation]) -> tuple[SectorComponentObservation, ...]:
    selected: dict[str, SectorComponentObservation] = {}
    for row in sorted(rows, key=_dedupe_sort_key):
        selected[row.component_name] = row
    return tuple(selected[name] for name in sorted(selected))


def _dedupe_sort_key(row: SectorComponentObservation) -> tuple[str, date, datetime, str]:
    return (row.component_name, row.as_of_date, row.available_at, row.data_snapshot_id)


def _snapshot_warnings(
    *,
    sector_id: str,
    decision_date: date,
    available_at: datetime,
    data_snapshot_id: str,
    parameter_version: str,
    model_version: str,
    observations: Sequence[SectorComponentObservation],
    stale_after_days: int | None,
) -> list[SectorComponentValidationWarning]:
    warnings: list[SectorComponentValidationWarning] = []
    for row in observations:
        warnings.extend(row.warnings)
        if stale_after_days is not None and (decision_date - row.as_of_date).days > stale_after_days:
            warnings.append(
                SectorComponentValidationWarning(
                    sector_id=sector_id,
                    component_name=row.component_name,
                    as_of_date=decision_date,
                    available_at=available_at,
                    parameter_version=parameter_version,
                    model_version=model_version,
                    data_snapshot_id=data_snapshot_id,
                    reason_codes=("REVIEW_REQUIRED",),
                    warnings=("COMPONENT_STALE",),
                    code="COMPONENT_STALE",
                    message=f"{row.component_name} stale by {(decision_date - row.as_of_date).days} days",
                )
            )
    return warnings


def _decision_time(decision_date: date) -> datetime:
    return datetime.combine(decision_date, time.max, tzinfo=UTC)


def _snapshot_id(sector_id: str, decision_date: date, parameter_version: str) -> str:
    return f"sector-component:{sector_id}:{decision_date.isoformat()}:{parameter_version}"

