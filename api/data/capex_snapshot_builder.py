from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Sequence

from api.data.capex_models import RawCompanyMetricPoint, RawTimeSeriesPoint
from api.data.capex_ports import CapexRawDataRepository
from api.score_pipeline.contracts import DataQualityMetadata, DecisionWarning
from api.score_pipeline.data_quality import DataQualityAssessor, HistoricalSnapshot, RawDataPoint


@dataclass(frozen=True)
class CapexSnapshotPointMetadata:
    key: str
    metric_id: str
    source: str
    source_id: str
    unit: str
    available_at: datetime
    updated_at: datetime
    revision_id: str | None
    quality: DataQualityMetadata


@dataclass(frozen=True)
class CapexRawSnapshot:
    snapshot: HistoricalSnapshot
    point_metadata: dict[str, CapexSnapshotPointMetadata]
    missing_metrics: tuple[str, ...] = ()

    @property
    def snapshot_id(self) -> str:
        return self.snapshot.snapshot_id

    @property
    def decision_date(self):
        return self.snapshot.decision_date

    @property
    def points(self) -> dict[str, RawDataPoint]:
        return self.snapshot.points

    @property
    def warnings(self) -> list[DecisionWarning]:
        return self.snapshot.warnings

    def get_available(self, key: str) -> RawDataPoint | None:
        return self.snapshot.get_available(key)


@dataclass
class CapexRawSnapshotBuilder:
    repository: CapexRawDataRepository
    stale_after_days_by_metric: Mapping[str, int] | None = None

    def build(
        self,
        *,
        decision_time: datetime,
        metric_ids: Sequence[str],
        snapshot_id: str | None = None,
        company_metric_ids: Mapping[str, Sequence[str]] | None = None,
    ) -> CapexRawSnapshot:
        stale_after_days = dict(self.stale_after_days_by_metric or {})
        points: dict[str, RawDataPoint] = {}
        metadata: dict[str, CapexSnapshotPointMetadata] = {}
        warnings: list[DecisionWarning] = []
        missing: list[str] = []

        for metric_id in metric_ids:
            rows = self.repository.read_time_series(metric_id=metric_id, as_of=decision_time)
            selected = _latest_time_series(rows, decision_time)
            if selected is None:
                _record_missing(metric_id, decision_time, warnings, missing, metadata)
                continue
            key = metric_id
            point, point_metadata = _raw_time_series_point(
                key=key,
                row=selected,
                decision_time=decision_time,
                stale_after_days=stale_after_days.get(metric_id, 36500),
            )
            points[key] = point
            metadata[key] = point_metadata

        for company_id, requested_metric_ids in (company_metric_ids or {}).items():
            for metric_id in requested_metric_ids:
                rows = self.repository.read_company_metrics(
                    company_id=company_id,
                    metric_id=metric_id,
                    as_of=decision_time,
                )
                selected = _latest_company_metric(rows, decision_time)
                key = f"{company_id}:{metric_id}"
                if selected is None:
                    _record_missing(key, decision_time, warnings, missing, metadata)
                    continue
                point, point_metadata = _raw_company_metric_point(
                    key=key,
                    row=selected,
                    decision_time=decision_time,
                    stale_after_days=stale_after_days.get(metric_id, 36500),
                )
                points[key] = point
                metadata[key] = point_metadata

        resolved_snapshot_id = snapshot_id or _snapshot_id(decision_time, points.keys(), missing)
        snapshot = HistoricalSnapshot(resolved_snapshot_id, decision_time.date(), points, warnings)
        return CapexRawSnapshot(snapshot=snapshot, point_metadata=metadata, missing_metrics=tuple(missing))


def _latest_time_series(rows: Sequence[RawTimeSeriesPoint], decision_time: datetime) -> RawTimeSeriesPoint | None:
    eligible = [row for row in rows if row.available_at <= decision_time]
    if not eligible:
        return None
    return max(eligible, key=lambda row: (row.observation_date, row.available_at, row.updated_at))


def _latest_company_metric(rows: Sequence[RawCompanyMetricPoint], decision_time: datetime) -> RawCompanyMetricPoint | None:
    eligible = [row for row in rows if row.available_at <= decision_time]
    if not eligible:
        return None
    return max(eligible, key=lambda row: (row.period, row.available_at, row.updated_at))


def _raw_time_series_point(
    *,
    key: str,
    row: RawTimeSeriesPoint,
    decision_time: datetime,
    stale_after_days: int,
) -> tuple[RawDataPoint, CapexSnapshotPointMetadata]:
    point = RawDataPoint(
        key=key,
        value=float(row.value),
        source=row.source,
        as_of_date=row.observation_date,
        available_at=row.available_at,
        updated_at=row.updated_at,
        revision_id=row.revision_id,
    )
    quality = _quality(row.source, decision_time, row.updated_at, point.value, stale_after_days)
    return point, CapexSnapshotPointMetadata(
        key=key,
        metric_id=row.metric_id,
        source=row.source,
        source_id=row.source_id,
        unit=row.unit,
        available_at=row.available_at,
        updated_at=row.updated_at,
        revision_id=row.revision_id,
        quality=quality,
    )


def _raw_company_metric_point(
    *,
    key: str,
    row: RawCompanyMetricPoint,
    decision_time: datetime,
    stale_after_days: int,
) -> tuple[RawDataPoint, CapexSnapshotPointMetadata]:
    point = RawDataPoint(
        key=key,
        value=float(row.value),
        source=row.source,
        as_of_date=decision_time.date(),
        available_at=row.available_at,
        updated_at=row.updated_at,
        revision_id=row.revision_id,
    )
    quality = _quality(row.source, decision_time, row.updated_at, point.value, stale_after_days)
    return point, CapexSnapshotPointMetadata(
        key=key,
        metric_id=row.metric_id,
        source=row.source,
        source_id=row.source_id,
        unit=row.unit,
        available_at=row.available_at,
        updated_at=row.updated_at,
        revision_id=row.revision_id,
        quality=quality,
    )


def _record_missing(
    key: str,
    decision_time: datetime,
    warnings: list[DecisionWarning],
    missing: list[str],
    metadata: dict[str, CapexSnapshotPointMetadata],
) -> None:
    warning = DecisionWarning("MISSING_RAW_METRIC", "WARNING", "capex_snapshot_builder", key)
    warnings.append(warning)
    missing.append(key)
    quality = DataQualityMetadata(
        source="missing",
        as_of_date=decision_time.date(),
        updated_at=decision_time,
        quality_score=0.0,
        missing_ratio=1.0,
        is_stale=True,
        warnings=[warning],
    )
    metadata[key] = CapexSnapshotPointMetadata(
        key=key,
        metric_id=key,
        source="missing",
        source_id="missing",
        unit="unknown",
        available_at=decision_time,
        updated_at=decision_time,
        revision_id=None,
        quality=quality,
    )


def _quality(
    source: str,
    decision_time: datetime,
    updated_at: datetime,
    value: float | None,
    stale_after_days: int,
) -> DataQualityMetadata:
    return DataQualityAssessor().assess(
        source=source,
        as_of_date=decision_time.date(),
        updated_at=updated_at,
        values=[value],
        stale_after_days=stale_after_days,
    )


def _snapshot_id(decision_time: datetime, keys: Sequence[str], missing: Sequence[str]) -> str:
    payload = {
        "decision_time": decision_time.isoformat(),
        "keys": sorted(keys),
        "missing": sorted(missing),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return f"capex_raw_snapshot_{decision_time.date().strftime('%Y%m%d')}_{digest}"
