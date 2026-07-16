from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import fmean
from typing import Iterable, Mapping

import yaml

from api.data.adapters.semiconductor_fixtures import FixtureSemiconductorObservationRepository
from api.domain.semiconductor_observations import SemiconductorObservation
from api.plugin_boundary.contracts import FeatureValue
from api.score_pipeline.contracts import PipelineContractError


@dataclass(frozen=True)
class SemiconductorDemandFeatureDefinitions:
    parameter_version: str
    model_version: str
    feature_version: str
    global_sales_series_id: str
    regional_series_ids: tuple[str, ...]
    product_category_series_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not all((self.parameter_version, self.model_version, self.feature_version, self.global_sales_series_id)):
            raise PipelineContractError("demand feature versions and global series id are required")
        if not self.regional_series_ids or not self.product_category_series_ids:
            raise PipelineContractError("configured region and product category series are required")


@dataclass(frozen=True)
class SemiconductorDemandFeatureSnapshot:
    snapshot_id: str
    as_of_date: datetime
    features: tuple[FeatureValue, ...]
    confidence: float
    missing_series_ids: tuple[str, ...]

    def by_id(self, feature_id: str) -> FeatureValue:
        return next(feature for feature in self.features if feature.feature_id == feature_id)


def load_semiconductor_demand_feature_definitions(path: str | Path) -> SemiconductorDemandFeatureDefinitions:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    metadata = raw.get("parameter_metadata") or {}
    inputs = raw.get("inputs") or {}
    try:
        return SemiconductorDemandFeatureDefinitions(
            parameter_version=str(metadata["parameter_version"]),
            model_version=str(metadata["model_version"]),
            feature_version=str(metadata["feature_version"]),
            global_sales_series_id=str(inputs["global_sales_series_id"]),
            regional_series_ids=tuple(str(value) for value in inputs["regional_series_ids"]),
            product_category_series_ids=tuple(str(value) for value in inputs["product_category_series_ids"]),
        )
    except (KeyError, TypeError) as exc:
        raise PipelineContractError("invalid semiconductor demand feature configuration") from exc


class SemiconductorDemandFeatureMaterializer:
    def __init__(self, definitions: SemiconductorDemandFeatureDefinitions) -> None:
        self._definitions = definitions

    def materialize(
        self,
        repository: FixtureSemiconductorObservationRepository,
        *,
        snapshot_id: str,
        decision_time: datetime,
    ) -> SemiconductorDemandFeatureSnapshot:
        global_observations = repository.select_available_series(
            self._definitions.global_sales_series_id,
            decision_time=decision_time,
        )
        feature_inputs = {
            "semiconductor.demand.monthly_sales_yoy": _monthly_yoy(global_observations),
            "semiconductor.demand.three_month_average_yoy": _three_month_average_yoy(global_observations),
            "semiconductor.demand.three_month_annualized_momentum": _three_month_annualized_momentum(global_observations),
            "semiconductor.demand.growth_acceleration": _growth_acceleration(global_observations),
            "semiconductor.demand.long_trend_deviation": _long_trend_deviation(global_observations),
        }
        missing: list[str] = []
        features = [
            self._feature(feature_id, value, global_observations, snapshot_id=snapshot_id, unit="ratio")
            for feature_id, value in feature_inputs.items()
        ]
        region_value, region_observations, region_missing = _breadth(
            repository,
            self._definitions.regional_series_ids,
            decision_time=decision_time,
        )
        product_value, product_observations, product_missing = _breadth(
            repository,
            self._definitions.product_category_series_ids,
            decision_time=decision_time,
        )
        missing.extend(region_missing)
        missing.extend(product_missing)
        features.append(
            self._feature(
                "semiconductor.demand.regional_breadth",
                region_value,
                region_observations,
                snapshot_id=snapshot_id,
                unit="fraction",
                coverage=(len(self._definitions.regional_series_ids) - len(region_missing)) / len(self._definitions.regional_series_ids),
            )
        )
        features.append(
            self._feature(
                "semiconductor.demand.product_category_breadth",
                product_value,
                product_observations,
                snapshot_id=snapshot_id,
                unit="fraction",
                coverage=(len(self._definitions.product_category_series_ids) - len(product_missing)) / len(self._definitions.product_category_series_ids),
            )
        )
        all_required = len(self._definitions.regional_series_ids) + len(self._definitions.product_category_series_ids)
        confidence = max(0.0, min(1.0, 1.0 - (len(missing) / max(all_required, 1))))
        return SemiconductorDemandFeatureSnapshot(
            snapshot_id=snapshot_id,
            as_of_date=decision_time,
            features=tuple(features),
            confidence=confidence,
            missing_series_ids=tuple(sorted(set(missing))),
        )

    def _feature(
        self,
        feature_id: str,
        value: float | None,
        observations: Iterable[SemiconductorObservation],
        *,
        snapshot_id: str,
        unit: str,
        coverage: float = 1.0,
    ) -> FeatureValue:
        rows = tuple(observations)
        missing = value is None
        quality = 0.0 if missing else min((row.quality.quality_score for row in rows), default=0.0) * coverage
        missing_ratio = 1.0 if missing else max(1.0 - coverage, sum(row.quality.missing for row in rows) / max(len(rows), 1))
        available_at = max((row.available_at for row in rows), default=datetime.min.replace(tzinfo=None))
        return FeatureValue(
            feature_id=feature_id,
            entity_type="universe",
            entity_id="SEMICONDUCTOR_ACTIVE_OVERLAY",
            feature_value=value,
            unit=unit,
            as_of_date=available_at.date(),
            available_at=available_at,
            source_dataset_ids=[snapshot_id],
            source_plugin_ids=[],
            calculation_method=feature_id.rsplit(".", 1)[-1],
            feature_version=self._definitions.feature_version,
            parameter_version=self._definitions.parameter_version,
            data_quality=quality,
            missing_ratio=missing_ratio,
            is_stale=any(row.quality.stale for row in rows),
            warnings=["SEMICONDUCTOR_DEMAND_FEATURE_UNAVAILABLE"] if missing else (["SEMICONDUCTOR_DEMAND_FEATURE_PARTIAL_COVERAGE"] if coverage < 1.0 else []),
            reason_codes=["SEMICONDUCTOR_DEMAND_FEATURE_REVIEW_REQUIRED"] if missing else (["SEMICONDUCTOR_DEMAND_FEATURE_PARTIAL_COVERAGE"] if coverage < 1.0 else ["SEMICONDUCTOR_DEMAND_FEATURE_MATERIALIZED"]),
            metadata={"model_version": self._definitions.model_version},
        )


def _monthly_yoy(rows: tuple[SemiconductorObservation, ...]) -> float | None:
    return _ratio_to_period(rows, periods=12)


def _three_month_average_yoy(rows: tuple[SemiconductorObservation, ...]) -> float | None:
    if len(rows) < 15:
        return None
    latest = rows[-3:]
    prior = rows[-15:-12]
    if any(row.value is None or float(row.value) <= 0 for row in prior):
        return None
    return (fmean(float(row.value) for row in latest) / fmean(float(row.value) for row in prior)) - 1.0


def _three_month_annualized_momentum(rows: tuple[SemiconductorObservation, ...]) -> float | None:
    ratio = _ratio_to_period(rows, periods=3)
    if ratio is None or ratio <= -1.0:
        return None
    return (1.0 + ratio) ** 4 - 1.0


def _growth_acceleration(rows: tuple[SemiconductorObservation, ...]) -> float | None:
    current = _monthly_yoy(rows)
    if current is None or len(rows) < 15:
        return None
    prior_yoy = [_ratio_to_period(rows[:index], periods=12) for index in range(len(rows) - 2, len(rows) + 1)]
    if any(value is None for value in prior_yoy):
        return None
    return current - fmean(float(value) for value in prior_yoy)


def _long_trend_deviation(rows: tuple[SemiconductorObservation, ...]) -> float | None:
    current = _monthly_yoy(rows)
    yoy_history = [_ratio_to_period(rows[:index], periods=12) for index in range(13, len(rows) + 1)]
    usable = [float(value) for value in yoy_history if value is not None]
    if current is None or len(usable) < 3:
        return None
    return current - fmean(usable)


def _ratio_to_period(rows: tuple[SemiconductorObservation, ...], *, periods: int) -> float | None:
    if len(rows) <= periods:
        return None
    latest = rows[-1].value
    prior = rows[-1 - periods].value
    if latest is None or prior is None or float(prior) <= 0:
        return None
    return (float(latest) / float(prior)) - 1.0


def _breadth(
    repository: FixtureSemiconductorObservationRepository,
    series_ids: tuple[str, ...],
    *,
    decision_time: datetime,
) -> tuple[float | None, tuple[SemiconductorObservation, ...], tuple[str, ...]]:
    values: list[float] = []
    observations: list[SemiconductorObservation] = []
    missing: list[str] = []
    for series_id in series_ids:
        series = repository.select_available_series(series_id, decision_time=decision_time)
        value = _monthly_yoy(series)
        if value is None:
            missing.append(series_id)
            continue
        values.append(value)
        observations.extend(series)
    if not values:
        return None, tuple(observations), tuple(missing)
    # Breadth remains a descriptive fraction; it is never mapped to an action.
    return sum(value > 0.0 for value in values) / len(values), tuple(observations), tuple(missing)
