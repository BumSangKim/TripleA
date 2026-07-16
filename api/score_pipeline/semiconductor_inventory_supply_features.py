from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import fmean

import yaml

from api.data.adapters.semiconductor_fixtures import FixtureSemiconductorObservationRepository
from api.domain.semiconductor_observations import SemiconductorObservation
from api.plugin_boundary.contracts import FeatureValue


@dataclass(frozen=True)
class InventorySupplyDefinitions:
    parameter_version: str
    model_version: str
    companies: tuple[str, ...]
    end_demand_series_id: str
    metrics: dict[str, str]


@dataclass(frozen=True)
class InventorySupplyFeatureSnapshot:
    features: tuple[FeatureValue, ...]
    coverage: float
    missing_series_ids: tuple[str, ...]


def load_inventory_supply_definitions(path: str | Path) -> InventorySupplyDefinitions:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    metadata, inputs = raw["parameter_metadata"], raw["inputs"]
    return InventorySupplyDefinitions(str(metadata["parameter_version"]), str(metadata["model_version"]), tuple(str(value) for value in inputs["companies"]), str(inputs["end_demand_series_id"]), {str(key): str(value) for key, value in inputs["metrics"].items()})


class InventorySupplyFeatureMaterializer:
    def __init__(self, definitions: InventorySupplyDefinitions) -> None:
        self._definitions = definitions

    def materialize(self, repository: FixtureSemiconductorObservationRepository, *, snapshot_id: str, decision_time: datetime) -> InventorySupplyFeatureSnapshot:
        series: dict[tuple[str, str], tuple[SemiconductorObservation, ...]] = {}
        missing: list[str] = []
        for company in self._definitions.companies:
            for metric, template in self._definitions.metrics.items():
                key = template.format(company=company)
                rows = repository.select_available_series(key, decision_time=decision_time)
                series[(company, metric)] = rows
                if not rows:
                    missing.append(key)
        demand = repository.select_available_series(self._definitions.end_demand_series_id, decision_time=decision_time)
        if not demand:
            missing.append(self._definitions.end_demand_series_id)
        inventory_percentiles = [_percentile(_values(rows)) for (_, metric), rows in series.items() if metric == "inventory_days" and _values(rows)]
        inventory_revenue_gaps = [_yoy(_values(series[(company, "inventory_days")])) - _yoy(_values(series[(company, "revenue")])) for company in self._definitions.companies if _yoy(_values(series[(company, "inventory_days")])) is not None and _yoy(_values(series[(company, "revenue")])) is not None]
        peak_distances = [_peak_distance(_values(rows)) for (_, metric), rows in series.items() if metric == "inventory_days" and _peak_distance(_values(rows)) is not None]
        normalization_speeds = [_normalization_speed(_values(rows)) for (_, metric), rows in series.items() if metric == "inventory_days" and _normalization_speed(_values(rows)) is not None]
        utilization_gaps = [_latest_minus_mean(_values(rows)) for (_, metric), rows in series.items() if metric == "utilization" and _latest_minus_mean(_values(rows)) is not None]
        capacity_growth = [_yoy(_values(rows)) for (_, metric), rows in series.items() if metric == "capacity" and _yoy(_values(rows)) is not None]
        bit_growth = [_yoy(_values(rows)) for (_, metric), rows in series.items() if metric == "bit_growth" and _yoy(_values(rows)) is not None]
        capex_growth = [_yoy(_values(rows)) for (_, metric), rows in series.items() if metric == "capex" and _yoy(_values(rows)) is not None]
        demand_growth = _yoy(_values(demand))
        values = {
            "semiconductor.supply.inventory_days_percentile": _mean(inventory_percentiles),
            "semiconductor.supply.inventory_growth_minus_revenue_growth": _mean(inventory_revenue_gaps),
            "semiconductor.supply.inventory_peak_distance": _mean(peak_distances),
            "semiconductor.supply.inventory_normalization_speed": _mean(normalization_speeds),
            "semiconductor.supply.utilization_gap": _mean(utilization_gaps),
            "semiconductor.supply.capacity_growth": _mean(capacity_growth),
            "semiconductor.supply.bit_growth": _mean(bit_growth),
            "semiconductor.supply.producer_capex_breadth": None if not capex_growth else sum(value > 0 for value in capex_growth) / len(capex_growth),
            "semiconductor.supply.supply_discipline": None if not capacity_growth and not bit_growth else -_mean([*capacity_growth, *bit_growth]),
            "semiconductor.supply.effective_supply_minus_end_demand_growth": None if demand_growth is None or not capacity_growth and not bit_growth else _mean([*capacity_growth, *bit_growth]) - demand_growth,
        }
        coverage = 1.0 - (len(missing) / max(len(self._definitions.companies) * len(self._definitions.metrics) + 1, 1))
        rows = tuple(row for item in series.values() for row in item) + tuple(demand)
        return InventorySupplyFeatureSnapshot(tuple(_feature(feature_id, value, rows, snapshot_id, self._definitions, coverage) for feature_id, value in values.items()), coverage, tuple(sorted(set(missing))))


def _values(rows: tuple[SemiconductorObservation, ...]) -> list[float]: return [float(row.value) for row in rows if row.value is not None]
def _mean(values: list[float | None]) -> float | None:
    usable = [float(value) for value in values if value is not None]
    return fmean(usable) if usable else None
def _yoy(values: list[float]) -> float | None: return None if len(values) < 5 or values[-5] == 0 else (values[-1] / values[-5]) - 1.0
def _percentile(values: list[float]) -> float | None: return None if not values else (sum(value < values[-1] for value in values) + 0.5 * sum(value == values[-1] for value in values)) / len(values)
def _peak_distance(values: list[float]) -> float | None: return None if not values or max(values) == 0 else (values[-1] / max(values)) - 1.0
def _normalization_speed(values: list[float]) -> float | None: return None if len(values) < 2 or values[-2] == 0 else -((values[-1] / values[-2]) - 1.0)
def _latest_minus_mean(values: list[float]) -> float | None: return None if not values else values[-1] - fmean(values)
def _feature(feature_id: str, value: float | None, rows: tuple[SemiconductorObservation, ...], snapshot_id: str, definitions: InventorySupplyDefinitions, coverage: float) -> FeatureValue:
    available_at = max((row.available_at for row in rows), default=datetime.min)
    return FeatureValue(feature_id, "universe", "SEMICONDUCTOR_ACTIVE_OVERLAY", value, "ratio" if "breadth" not in feature_id and "percentile" not in feature_id else "fraction", available_at.date(), available_at, [snapshot_id], [], feature_id.rsplit(".", 1)[-1], "semiconductor_inventory_supply_features_v1", definitions.parameter_version, coverage if value is not None else 0.0, 0.0 if value is not None else 1.0, any(row.quality.stale for row in rows), ["INVENTORY_SUPPLY_FEATURE_UNAVAILABLE"] if value is None else [], ["INVENTORY_SUPPLY_REVIEW_REQUIRED"] if value is None else ["INVENTORY_SUPPLY_FEATURE_MATERIALIZED"], {"model_version": definitions.model_version, "coverage": coverage})
