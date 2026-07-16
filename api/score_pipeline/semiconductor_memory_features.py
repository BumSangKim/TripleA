from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import yaml

from api.data.adapters.semiconductor_fixtures import FixtureSemiconductorObservationRepository
from api.domain.semiconductor_observations import SemiconductorObservation
from api.plugin_boundary.contracts import FeatureValue
from api.score_pipeline.normalization_primitives import NormalizationParameters, normalize_signal


@dataclass(frozen=True)
class MemorySeriesDefinition:
    series_id: str
    product: str
    price_type: str
    frequency: str
    optional: bool


@dataclass(frozen=True)
class MemoryPriceFeatureDefinitions:
    parameter_version: str
    model_version: str
    series: tuple[MemorySeriesDefinition, ...]


@dataclass(frozen=True)
class MemoryPriceFeatureSnapshot:
    features: tuple[FeatureValue, ...]
    confidence: float
    missing_optional_series: tuple[str, ...]


def load_memory_price_feature_definitions(path: str | Path) -> MemoryPriceFeatureDefinitions:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    metadata = raw["parameter_metadata"]
    return MemoryPriceFeatureDefinitions(
        parameter_version=str(metadata["parameter_version"]),
        model_version=str(metadata["model_version"]),
        series=tuple(MemorySeriesDefinition(str(row["id"]), str(row["product"]), str(row["price_type"]), str(row["frequency"]), bool(row["optional"])) for row in raw["series"]),
    )


class MemoryPriceFeatureMaterializer:
    def __init__(self, definitions: MemoryPriceFeatureDefinitions, normalization: NormalizationParameters) -> None:
        self._definitions = definitions
        self._normalization = normalization

    def materialize(self, repository: FixtureSemiconductorObservationRepository, *, snapshot_id: str, decision_time: datetime) -> MemoryPriceFeatureSnapshot:
        features: list[FeatureValue] = []
        missing_optional: list[str] = []
        available: dict[tuple[str, str], tuple[SemiconductorObservation, ...]] = {}
        for definition in self._definitions.series:
            rows = repository.select_available_series(definition.series_id, decision_time=decision_time)
            available[(definition.product, definition.price_type)] = rows
            if not rows and definition.optional:
                missing_optional.append(definition.series_id)
            for months in (1, 3, 6):
                features.append(self._momentum_feature(definition, rows, months, snapshot_id))
            features.append(self._acceleration_feature(definition, rows, snapshot_id))
        for product in sorted({definition.product for definition in self._definitions.series}):
            spot = available.get((product, "spot"), ())
            contract = available.get((product, "contract"), ())
            if spot or contract:
                features.append(self._spread_feature(product, spot, contract, snapshot_id))
        features.append(self._breadth_feature(available, snapshot_id))
        coverage = 1.0 - (len(missing_optional) / max(len(self._definitions.series), 1))
        return MemoryPriceFeatureSnapshot(tuple(features), coverage, tuple(missing_optional))

    def _momentum_feature(self, definition: MemorySeriesDefinition, rows: tuple[SemiconductorObservation, ...], months: int, snapshot_id: str) -> FeatureValue:
        returns = _returns(rows, months)
        raw = returns[-1] if returns else None
        result = normalize_signal(raw_value=raw, history=returns, prior_normalized_scores=(), frequency=definition.frequency, data_quality=_quality(rows), source_confidence=1.0, parameters=self._normalization)
        return _feature(
            f"semiconductor.memory.{definition.product}.{definition.price_type}.momentum_{months}m",
            result.smoothed_score if raw is not None else None,
            snapshot_id,
            rows,
            self._definitions,
            unit="normalized_ratio",
            metadata={"raw_momentum": raw, "normalization_reason_codes": result.reason_codes, "price_type": definition.price_type},
            warnings=list(result.reason_codes),
        )

    def _acceleration_feature(self, definition: MemorySeriesDefinition, rows: tuple[SemiconductorObservation, ...], snapshot_id: str) -> FeatureValue:
        one_month = _returns(rows, 1)
        acceleration = one_month[-1] - one_month[-2] if len(one_month) >= 2 else None
        history = [one_month[index] - one_month[index - 1] for index in range(1, len(one_month))]
        result = normalize_signal(raw_value=acceleration, history=history, prior_normalized_scores=(), frequency=definition.frequency, data_quality=_quality(rows), source_confidence=1.0, parameters=self._normalization)
        return _feature(f"semiconductor.memory.{definition.product}.{definition.price_type}.price_acceleration", result.smoothed_score if acceleration is not None else None, snapshot_id, rows, self._definitions, unit="normalized_ratio", metadata={"raw_acceleration": acceleration, "price_type": definition.price_type}, warnings=list(result.reason_codes))

    def _spread_feature(self, product: str, spot: tuple[SemiconductorObservation, ...], contract: tuple[SemiconductorObservation, ...], snapshot_id: str) -> FeatureValue:
        raw = None
        if spot and contract and spot[-1].value is not None and contract[-1].value not in {None, 0}:
            raw = (float(spot[-1].value) / float(contract[-1].value)) - 1.0
        return _feature(f"semiconductor.memory.{product}.spot_contract_spread", raw, snapshot_id, (*spot, *contract), self._definitions, unit="ratio", metadata={"spot_series_present": bool(spot), "contract_series_present": bool(contract)}, warnings=[] if raw is not None else ["MEMORY_SPOT_CONTRACT_SPREAD_UNAVAILABLE"])

    def _breadth_feature(self, available: dict[tuple[str, str], tuple[SemiconductorObservation, ...]], snapshot_id: str) -> FeatureValue:
        product_returns = [_returns(rows, 3)[-1] for (_, _), rows in available.items() if _returns(rows, 3)]
        raw = None if not product_returns else sum(value > 0 for value in product_returns) / len(product_returns)
        rows = tuple(row for series in available.values() for row in series)
        return _feature("semiconductor.memory.product_breadth", raw, snapshot_id, rows, self._definitions, unit="fraction", metadata={"available_series_count": len(product_returns)}, warnings=[] if raw is not None else ["MEMORY_PRODUCT_BREADTH_UNAVAILABLE"])


def _returns(rows: tuple[SemiconductorObservation, ...], months: int) -> list[float]:
    values = [float(row.value) if row.value is not None else None for row in rows]
    return [(values[index] / values[index - months]) - 1.0 for index in range(months, len(values)) if values[index] is not None and values[index - months] not in {None, 0}]


def _quality(rows: Iterable[SemiconductorObservation]) -> float:
    values = [row.quality.quality_score for row in rows]
    return min(values, default=0.0)


def _feature(feature_id: str, value: float | None, snapshot_id: str, rows: Iterable[SemiconductorObservation], definitions: MemoryPriceFeatureDefinitions, *, unit: str, metadata: dict[str, object], warnings: list[str]) -> FeatureValue:
    items = tuple(rows)
    available_at = max((row.available_at for row in items), default=datetime.min)
    return FeatureValue(feature_id=feature_id, entity_type="universe", entity_id="SEMICONDUCTOR_ACTIVE_OVERLAY", feature_value=value, unit=unit, as_of_date=available_at.date(), available_at=available_at, source_dataset_ids=[snapshot_id], source_plugin_ids=[], calculation_method=feature_id.rsplit(".", 1)[-1], feature_version="semiconductor_memory_price_features_v1", parameter_version=definitions.parameter_version, data_quality=_quality(items) if value is not None else 0.0, missing_ratio=0.0 if value is not None else 1.0, is_stale=any(row.quality.stale for row in items), warnings=warnings, reason_codes=["MEMORY_PRICE_FEATURE_MATERIALIZED"] if value is not None else ["MEMORY_PRICE_FEATURE_REVIEW_REQUIRED"], metadata={**metadata, "model_version": definitions.model_version})
