from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from api.new_pipeline.contracts import DecisionWarning, FeatureOutput, ReasonCode, clamp_ratio
from api.new_pipeline.data_quality import DataQualityAssessor, HistoricalSnapshot
from api.new_pipeline.parameters import ParameterRegistry


class FeaturePlugin(Protocol):
    feature_id: str

    def compute(self, snapshot: HistoricalSnapshot, registry: ParameterRegistry) -> FeatureOutput:
        ...


@dataclass(frozen=True)
class FeaturePluginConfig:
    feature_id: str
    enabled: bool = True


class FeatureRegistry:
    def __init__(self):
        self._plugins: dict[str, FeaturePlugin] = {}
        self._enabled: dict[str, bool] = {}

    def register(self, plugin: FeaturePlugin, *, enabled: bool = True) -> None:
        self._plugins[plugin.feature_id] = plugin
        self._enabled[plugin.feature_id] = enabled

    def run_enabled(self, snapshot: HistoricalSnapshot, registry: ParameterRegistry) -> list[FeatureOutput]:
        outputs: list[FeatureOutput] = []
        for feature_id, plugin in self._plugins.items():
            if self._enabled.get(feature_id, True):
                outputs.append(plugin.compute(snapshot, registry))
        return outputs

    def plugin_ids(self) -> set[str]:
        return set(self._plugins)


@dataclass(frozen=True)
class PriceMomentumFeaturePlugin:
    feature_id: str = "price_momentum_feature"
    feature_name: str = "Price Momentum Feature"
    asset_id: str = "SPY"
    start_key: str = "price_start"
    end_key: str = "price_end"

    def compute(self, snapshot: HistoricalSnapshot, registry: ParameterRegistry) -> FeatureOutput:
        parameter_version = registry.parameter_version_for(["lookback_window_days"], snapshot.decision_date)
        warnings: list[DecisionWarning] = []
        try:
            start = snapshot.get_available(self.start_key)
            end = snapshot.get_available(self.end_key)
        except Exception:
            start = end = None
            warnings.append(DecisionWarning("FUTURE_DATA_REJECTED", "BLOCKER", "feature", self.feature_id))
        values = [None if point is None else point.value for point in [start, end]]
        updated_at = max((point.updated_at for point in [start, end] if point is not None), default=None)
        if updated_at is None:
            from datetime import UTC, datetime
            updated_at = datetime.combine(snapshot.decision_date, datetime.min.time(), tzinfo=UTC)
        quality = DataQualityAssessor().assess(
            source="feature_snapshot",
            as_of_date=snapshot.decision_date,
            updated_at=updated_at,
            values=values,
            stale_after_days=14,
        )
        warnings.extend(quality.warnings)
        if start is None or end is None or start.value in {None, 0} or end.value is None:
            raw_value = None
            normalized = 0.5
            warnings.append(DecisionWarning("FEATURE_FALLBACK_NEUTRAL", "WARNING", "feature", "missing price input"))
        else:
            raw_value = (float(end.value) / float(start.value)) - 1.0
            normalized = clamp_ratio(0.5 + raw_value)
        return FeatureOutput(
            feature_id=self.feature_id,
            feature_name=self.feature_name,
            entity_id=self.asset_id,
            entity_type="asset",
            raw_value=raw_value,
            normalized_value=normalized,
            confidence=quality.quality_score,
            data_quality=quality,
            as_of_date=snapshot.decision_date,
            source="price",
            parameter_version=parameter_version,
            model_version="new_pipeline_feature_v1",
            reason_codes=[ReasonCode("FEATURE_PLUGIN_EXECUTED", "feature")],
            warnings=warnings,
        )
