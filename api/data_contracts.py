from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class DataQualityMeta:
    source: str
    as_of_date: date
    updated_at: datetime
    quality_score: float
    missing_ratio: float
    is_stale: bool
    coverage_ratio: float
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DataSnapshotRef:
    snapshot_id: str
    as_of_date: date
    source_tables: list[str]
    created_at: datetime
    data_cutoff_at: datetime


@dataclass(frozen=True)
class ParameterVersionRef:
    parameter_set_id: str
    version: str
    created_at: datetime


@dataclass(frozen=True)
class ModelVersionRef:
    model_name: str
    version: str
    created_at: datetime


@dataclass(frozen=True)
class ExperimentRunRef:
    run_id: str
    experiment_type: str
    created_at: datetime


@dataclass(frozen=True)
class RawDataPoint:
    entity_type: str
    entity_id: str
    metric_name: str
    value: float | str | None
    as_of_date: date
    source: str
    data_quality: DataQualityMeta


@dataclass(frozen=True)
class FeatureDataPoint:
    entity_type: str
    entity_id: str
    feature_name: str
    feature_value: float
    as_of_date: date
    data_quality: DataQualityMeta
    snapshot: DataSnapshotRef


@dataclass(frozen=True)
class ScoreDataPoint:
    entity_type: str
    entity_id: str
    score_name: str
    score_value: float
    confidence: float
    data_quality: DataQualityMeta
    as_of_date: date
    parameter_version: ParameterVersionRef
    model_version: ModelVersionRef
    reason_codes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DecisionDataPoint:
    decision_id: str
    as_of_date: date
    snapshot: DataSnapshotRef
    scores: list[ScoreDataPoint]
    decision_payload: dict[str, Any]
    reason_codes: list[str] = field(default_factory=list)
