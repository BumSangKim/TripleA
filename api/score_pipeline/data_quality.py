from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from statistics import mean, pstdev
from typing import Any

from api.score_pipeline.contracts import (
    ConservativeAction,
    DataQualityMetadata,
    DecisionWarning,
    PipelineContractError,
)


@dataclass(frozen=True)
class RawDataPoint:
    key: str
    value: float | None
    source: str
    as_of_date: date
    available_at: datetime
    updated_at: datetime
    revision_id: str | None = None


@dataclass(frozen=True)
class HistoricalSnapshot:
    snapshot_id: str
    decision_date: date
    points: dict[str, RawDataPoint]
    warnings: list[DecisionWarning] = field(default_factory=list)

    def get_available(self, key: str) -> RawDataPoint | None:
        point = self.points.get(key)
        if point is None:
            return None
        if point.available_at.date() > self.decision_date:
            raise PipelineContractError("future data is unavailable at simulated decision date")
        return point


class DataQualityAssessor:
    def assess(
        self,
        *,
        source: str,
        as_of_date: date,
        updated_at: datetime,
        values: list[float | None],
        stale_after_days: int,
    ) -> DataQualityMetadata:
        warnings: list[DecisionWarning] = []
        if not values:
            missing_ratio = 1.0
        else:
            missing_ratio = sum(1 for value in values if value is None) / len(values)
        is_stale = updated_at.date() + timedelta(days=stale_after_days) < as_of_date
        if missing_ratio > 0:
            warnings.append(DecisionWarning("MISSING_DATA", "WARNING", "data_quality", "missing values detected"))
        if is_stale:
            warnings.append(DecisionWarning("STALE_DATA", "WARNING", "data_quality", "data is stale"))
        numeric = [float(value) for value in values if value is not None]
        anomaly = _has_anomaly(numeric)
        if anomaly:
            warnings.append(DecisionWarning("ANOMALOUS_DATA", "WARNING", "data_quality", "outlier values detected"))
        quality = max(0.0, 1.0 - missing_ratio)
        if is_stale:
            quality *= 0.7
        if anomaly:
            quality *= 0.8
        return DataQualityMetadata(
            source=source,
            as_of_date=as_of_date,
            updated_at=updated_at,
            quality_score=quality,
            missing_ratio=missing_ratio,
            is_stale=is_stale,
            warnings=warnings,
        )


class SnapshotBuilder:
    def build(self, snapshot_id: str, decision_date: date, points: list[RawDataPoint]) -> HistoricalSnapshot:
        accepted: dict[str, RawDataPoint] = {}
        warnings: list[DecisionWarning] = []
        for point in points:
            if point.available_at.date() > decision_date:
                warnings.append(DecisionWarning("FUTURE_DATA_REJECTED", "BLOCKER", "snapshot", point.key))
                continue
            accepted[point.key] = point
        return HistoricalSnapshot(snapshot_id, decision_date, accepted, warnings)


def conservative_action_for_quality(metadata: DataQualityMetadata) -> str | None:
    if metadata.conservative_action:
        return metadata.conservative_action
    if any(warning.code == "ANOMALOUS_DATA" for warning in metadata.warnings):
        return ConservativeAction.REVIEW_REQUIRED
    return None


def _has_anomaly(values: list[float]) -> bool:
    if len(values) < 4:
        return False
    sigma = pstdev(values)
    if sigma <= 0:
        return False
    center = mean(values)
    return any(abs(value - center) / sigma > 3.0 for value in values)
