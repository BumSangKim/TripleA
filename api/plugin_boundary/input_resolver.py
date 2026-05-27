from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from api.plugin_boundary.contracts import PluginBoundaryContractError, PluginDataset
from api.plugin_boundary.registry import PluginRegistry
from api.plugin_boundary.time_guard import is_available_for_decision


@dataclass(frozen=True)
class FeatureSpec:
    feature_id: str
    mode: str
    entity_type: str
    required_dataset_types: tuple[str, ...]
    calculator: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    required_plugins: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.feature_id.strip():
            raise PluginBoundaryContractError("feature_id must be non-empty")
        if self.mode == "reusable_calculator" and self.required_plugins:
            raise PluginBoundaryContractError("reusable FeatureSpec must not use required_plugins")
        if self.mode == "reusable_calculator" and not self.required_dataset_types:
            raise PluginBoundaryContractError("reusable FeatureSpec requires dataset types")


@dataclass(frozen=True)
class PluginSignalSpec:
    signal_id: str
    mode: str
    required_plugins: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        if self.mode != "plugin_signal":
            raise PluginBoundaryContractError("PluginSignalSpec mode must be plugin_signal")
        if not self.required_plugins:
            raise PluginBoundaryContractError("PluginSignalSpec requires explicit plugins")
        if not self.reason.strip():
            raise PluginBoundaryContractError("PluginSignalSpec requires a reason")


@dataclass(frozen=True)
class FeatureInputResolution:
    datasets_by_type: dict[str, PluginDataset]
    fallback_used: bool = False
    reason_codes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class FeatureInputResolver:
    def __init__(self, registry: PluginRegistry, datasets: list[PluginDataset]):
        self.registry = registry
        self.datasets = datasets

    def resolve(
        self,
        spec: FeatureSpec,
        *,
        entity_id: str | None,
        decision_time: datetime,
    ) -> FeatureInputResolution:
        selected: dict[str, PluginDataset] = {}
        reason_codes: list[str] = []
        warnings: list[str] = []
        for dataset_type in spec.required_dataset_types:
            candidates = self._eligible_datasets(dataset_type, spec.entity_type, entity_id, decision_time)
            if not candidates:
                reason_codes.append("PLUGIN_DATASET_FALLBACK_USED")
                warnings.append(f"PLUGIN_DATASET_UNAVAILABLE:{dataset_type}")
                continue
            selected[dataset_type] = candidates[0]
        return FeatureInputResolution(
            datasets_by_type=selected,
            fallback_used=len(selected) != len(spec.required_dataset_types),
            reason_codes=reason_codes,
            warnings=warnings,
        )

    def _eligible_datasets(
        self,
        dataset_type: str,
        entity_type: str,
        entity_id: str | None,
        decision_time: datetime,
    ) -> list[PluginDataset]:
        provider_rank = {
            plugin.plugin_id: index
            for index, plugin in enumerate(self.registry.candidates_for_dataset_type(dataset_type))
        }
        candidates = [
            dataset
            for dataset in self.datasets
            if dataset.dataset_type == dataset_type
            and dataset.entity_type == entity_type
            and dataset.entity_id == entity_id
            and dataset.plugin_id in provider_rank
            and is_available_for_decision(dataset, decision_time)
        ]
        return sorted(
            candidates,
            key=lambda dataset: (
                provider_rank[dataset.plugin_id],
                -dataset.quality_score,
                -dataset.retrieved_at.timestamp(),
                dataset.dataset_id,
            ),
        )
