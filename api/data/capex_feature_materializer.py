from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from api.data.capex_snapshot_builder import CapexRawSnapshot, CapexSnapshotPointMetadata
from api.score_pipeline.contracts import DecisionWarning, PipelineContractError
from api.score_pipeline.data_quality import HistoricalSnapshot, RawDataPoint
from api.score_pipeline.plugins.ai_capex_cycle import REQUIRED_INPUTS as AI_REQUIRED_INPUTS
from api.score_pipeline.plugins.bio_capex_bottleneck import (
    DEMAND_MOMENTUM_COMPONENTS,
    FINANCIAL_QUALITY_COMPONENTS,
    RISK_PENALTY_COMPONENTS,
    STRUCTURAL_MOAT_COMPONENTS,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_CATALOG_PATH = PROJECT_ROOT / "config" / "data_sources" / "capex_cycle_sources.yaml"

AI_INPUT_MAPPING: dict[str, tuple[str, ...]] = {
    "bigtech_ai_capex_yoy": ("bigtech_ai_capex_yoy", "ai.capex.yoy"),
    "bigtech_ai_capex_accel": ("bigtech_ai_capex_accel", "ai.capex.acceleration"),
    "token_proxy_index": ("token_proxy_index", "ai.token_proxy.index"),
    "token_proxy_index_prev": ("token_proxy_index_prev", "ai.token_proxy.index.prev"),
}

BIO_INPUT_MAPPING: dict[str, tuple[str, ...]] = {
    **{key: (key,) for key in STRUCTURAL_MOAT_COMPONENTS},
    "segment_growth": ("segment_growth", "company.segment.growth"),
    "order_growth": ("order_growth", "company.order_backlog.growth"),
    "backlog_growth": ("backlog_growth", "company.order_backlog.growth"),
    "book_to_bill": ("book_to_bill", "company.book_to_bill"),
    "consumables_growth": ("consumables_growth", "company.consumables.growth"),
    "inventory_normalization": ("inventory_normalization",),
    **{key: (key, "company.margins") for key in FINANCIAL_QUALITY_COMPONENTS},
    **{key: (key, "company.risk_penalty.inputs") for key in RISK_PENALTY_COMPONENTS},
}


@dataclass(frozen=True)
class CapexMaterializedSnapshot:
    snapshot: HistoricalSnapshot
    missing_inputs: tuple[str, ...]
    review_required: tuple[str, ...]
    confidence: float

    @property
    def points(self) -> dict[str, RawDataPoint]:
        return self.snapshot.points

    @property
    def warnings(self) -> list[DecisionWarning]:
        return self.snapshot.warnings

    def get_available(self, key: str) -> RawDataPoint | None:
        return self.snapshot.get_available(key)


@dataclass
class CapexFeatureMaterializer:
    source_catalog_path: Path = SOURCE_CATALOG_PATH

    def materialize_ai(self, raw_snapshot: CapexRawSnapshot | HistoricalSnapshot) -> CapexMaterializedSnapshot:
        return self._materialize(
            raw_snapshot,
            required_inputs=AI_REQUIRED_INPUTS,
            mapping=AI_INPUT_MAPPING,
            snapshot_suffix="ai",
        )

    def materialize_bio(self, raw_snapshot: CapexRawSnapshot | HistoricalSnapshot) -> CapexMaterializedSnapshot:
        return self._materialize(
            raw_snapshot,
            required_inputs=tuple(BIO_INPUT_MAPPING),
            mapping=BIO_INPUT_MAPPING,
            snapshot_suffix="bio",
        )

    def _materialize(
        self,
        raw_snapshot: CapexRawSnapshot | HistoricalSnapshot,
        *,
        required_inputs: Sequence[str],
        mapping: Mapping[str, Sequence[str]],
        snapshot_suffix: str,
    ) -> CapexMaterializedSnapshot:
        source_snapshot = _snapshot(raw_snapshot)
        metadata = _metadata(raw_snapshot)
        units_by_metric = _catalog_units(self.source_catalog_path)
        points: dict[str, RawDataPoint] = {}
        warnings: list[DecisionWarning] = list(source_snapshot.warnings)
        missing: list[str] = []
        review_required: list[str] = []

        for target_key in required_inputs:
            materialized = self._resolve_point(
                source_snapshot,
                metadata,
                units_by_metric,
                target_key=target_key,
                candidates=mapping[target_key],
                warnings=warnings,
                review_required=review_required,
            )
            if materialized is None:
                missing.append(target_key)
                warnings.append(
                    DecisionWarning(
                        "CAPEX_MATERIALIZER_MISSING_INPUT",
                        "WARNING",
                        "capex_feature_materializer",
                        target_key,
                    )
                )
                continue
            points[target_key] = materialized

        confidence = 1.0 - (len(missing) / max(len(required_inputs), 1))
        snapshot = HistoricalSnapshot(
            snapshot_id=f"{source_snapshot.snapshot_id}:{snapshot_suffix}",
            decision_date=source_snapshot.decision_date,
            points=points,
            warnings=warnings,
        )
        return CapexMaterializedSnapshot(
            snapshot=snapshot,
            missing_inputs=tuple(missing),
            review_required=tuple(review_required),
            confidence=max(0.0, min(1.0, confidence)),
        )

    def _resolve_point(
        self,
        source_snapshot: HistoricalSnapshot,
        metadata: Mapping[str, CapexSnapshotPointMetadata],
        units_by_metric: Mapping[str, str],
        *,
        target_key: str,
        candidates: Sequence[str],
        warnings: list[DecisionWarning],
        review_required: list[str],
    ) -> RawDataPoint | None:
        for candidate in candidates:
            try:
                point = source_snapshot.get_available(candidate)
            except PipelineContractError:
                warnings.append(
                    DecisionWarning(
                        "CAPEX_MATERIALIZER_FUTURE_DATA_REJECTED",
                        "BLOCKER",
                        "capex_feature_materializer",
                        candidate,
                    )
                )
                continue
            if point is None:
                continue
            point_metadata = metadata.get(candidate)
            expected_unit = units_by_metric.get(candidate)
            if point_metadata is not None and expected_unit and point_metadata.unit != expected_unit:
                warnings.append(
                    DecisionWarning(
                        "CAPEX_MATERIALIZER_UNIT_REVIEW_REQUIRED",
                        "WARNING",
                        "capex_feature_materializer",
                        f"{candidate}: expected {expected_unit}, got {point_metadata.unit}",
                    )
                )
                review_required.append(target_key)
                return None
            return RawDataPoint(
                key=target_key,
                value=point.value,
                source=point.source,
                as_of_date=point.as_of_date,
                available_at=point.available_at,
                updated_at=point.updated_at,
                revision_id=point.revision_id,
            )
        return None


def _snapshot(value: CapexRawSnapshot | HistoricalSnapshot) -> HistoricalSnapshot:
    return value.snapshot if isinstance(value, CapexRawSnapshot) else value


def _metadata(value: CapexRawSnapshot | HistoricalSnapshot) -> Mapping[str, CapexSnapshotPointMetadata]:
    return value.point_metadata if isinstance(value, CapexRawSnapshot) else {}


def _catalog_units(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    units: dict[str, str] = {}
    for metric in (data.get("metrics") or {}).values():
        metric_id = metric.get("canonical_metric_id")
        unit = metric.get("unit")
        if metric_id and unit:
            units[str(metric_id)] = str(unit)
    return units
