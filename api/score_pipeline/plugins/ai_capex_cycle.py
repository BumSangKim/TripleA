from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from api.score_pipeline.contracts import DecisionWarning, FeatureOutput, PipelineContractError, ReasonCode
from api.score_pipeline.data_quality import DataQualityAssessor, HistoricalSnapshot, RawDataPoint
from api.score_pipeline.parameters import ParameterRegistry
from api.score_pipeline.plugins.capex_common import clamp, conservative_score_on_missing, safe_ratio, score_from_z, weighted_average


REQUIRED_INPUTS = (
    "bigtech_ai_capex_yoy",
    "bigtech_ai_capex_accel",
    "token_proxy_index",
    "token_proxy_index_prev",
)


@dataclass(frozen=True)
class AICapexCyclePlugin:
    feature_id: str = "feature:ai_capex_cycle"
    feature_name: str = "AI CapEx Cycle"
    entity_id: str = "ai_infrastructure"
    entity_type: str = "sector"

    def compute(self, snapshot: HistoricalSnapshot, registry: ParameterRegistry) -> FeatureOutput:
        warnings: list[DecisionWarning] = list(snapshot.warnings)
        reason_codes = [ReasonCode("AI_CAPEX_CYCLE_COMPUTED", "feature")]
        points: dict[str, RawDataPoint | None] = {}
        future_rejected = False
        for key in REQUIRED_INPUTS:
            try:
                points[key] = snapshot.get_available(key)
            except PipelineContractError:
                points[key] = None
                future_rejected = True
                warnings.append(DecisionWarning("AI_CAPEX_FUTURE_DATA_REJECTED", "BLOCKER", "feature", key))

        values = [None if point is None else point.value for point in points.values()]
        updated_at = max(
            (point.updated_at for point in points.values() if point is not None),
            default=datetime.combine(snapshot.decision_date, datetime.min.time(), tzinfo=UTC),
        )
        stale_days_lookup = registry.get("stale_after_days", as_of_date=snapshot.decision_date, expected_type=int)
        stale_after_days = int(stale_days_lookup.value) if stale_days_lookup.value is not None else 0
        warnings.extend(stale_days_lookup.warnings)
        quality = DataQualityAssessor().assess(
            source="ai_capex_cycle",
            as_of_date=snapshot.decision_date,
            updated_at=updated_at,
            values=values,
            stale_after_days=stale_after_days,
        )
        warnings.extend(quality.warnings)

        missing_required = future_rejected or any(value is None for value in values)
        if missing_required:
            reason_codes.append(ReasonCode("AI_CAPEX_DATA_MISSING", "feature"))
            fallback = conservative_score_on_missing()
            return self._output(
                snapshot=snapshot,
                normalized=float(fallback["score"]),
                raw_value=None,
                confidence=float(fallback["confidence"]),
                quality=quality,
                reason_codes=reason_codes,
                warnings=warnings,
                parameter_version=_parameter_version(registry, snapshot),
            )

        if quality.is_stale:
            reason_codes.append(ReasonCode("AI_CAPEX_DATA_STALE", "feature"))

        weight_lookup = registry.get("ai_cycle_weights", as_of_date=snapshot.decision_date, expected_type=dict)
        warnings.extend(weight_lookup.warnings)
        if weight_lookup.value is None:
            reason_codes.append(ReasonCode("AI_CAPEX_DATA_MISSING", "feature", "missing ai_cycle_weights"))
            fallback = conservative_score_on_missing()
            return self._output(
                snapshot=snapshot,
                normalized=float(fallback["score"]),
                raw_value=None,
                confidence=float(fallback["confidence"]),
                quality=quality,
                reason_codes=reason_codes,
                warnings=warnings,
                parameter_version=weight_lookup.version_ref.version,
            )

        capex_yoy = float(points["bigtech_ai_capex_yoy"].value)  # type: ignore[union-attr]
        capex_accel = float(points["bigtech_ai_capex_accel"].value)  # type: ignore[union-attr]
        token_current = float(points["token_proxy_index"].value)  # type: ignore[union-attr]
        token_previous = float(points["token_proxy_index_prev"].value)  # type: ignore[union-attr]
        token_change = token_current - token_previous
        tcr = safe_ratio(token_change, abs(token_previous))
        tce = safe_ratio(token_change, abs(capex_yoy))
        components = {
            "capex_growth": score_from_z(capex_yoy),
            "demand_momentum": score_from_z(tcr),
            "supply_constraint": score_from_z(capex_accel),
            "profitability_quality": score_from_z(tce),
            "data_quality": quality.quality_score,
        }
        normalized = weighted_average(components, weight_lookup.value)
        quality_min_lookup = registry.get("quality_min_required", as_of_date=snapshot.decision_date, expected_type=(int, float))
        warnings.extend(quality_min_lookup.warnings)
        quality_min = float(quality_min_lookup.value) if quality_min_lookup.value is not None else 1.0
        confidence = quality.quality_score
        if quality.quality_score < quality_min:
            warnings.append(
                DecisionWarning(
                    "AI_CAPEX_DATA_QUALITY_BELOW_MINIMUM",
                    "WARNING",
                    "feature",
                    f"quality={quality.quality_score:.4f}, min={quality_min:.4f}",
                )
            )
            confidence = min(confidence, 0.5)

        return self._output(
            snapshot=snapshot,
            normalized=normalized,
            raw_value=normalized,
            confidence=clamp(confidence),
            quality=quality,
            reason_codes=reason_codes,
            warnings=warnings,
            parameter_version=weight_lookup.version_ref.version,
        )

    def _output(
        self,
        *,
        snapshot: HistoricalSnapshot,
        normalized: float,
        raw_value: float | None,
        confidence: float,
        quality,
        reason_codes: list[ReasonCode],
        warnings: list[DecisionWarning],
        parameter_version: str,
    ) -> FeatureOutput:
        return FeatureOutput(
            feature_id=self.feature_id,
            feature_name=self.feature_name,
            entity_id=self.entity_id,
            entity_type=self.entity_type,
            raw_value=raw_value,
            normalized_value=clamp(normalized),
            confidence=clamp(confidence),
            data_quality=quality,
            as_of_date=snapshot.decision_date,
            source="ai_capex_cycle",
            parameter_version=parameter_version,
            model_version="ai_capex_cycle_plugin_v0",
            reason_codes=reason_codes,
            warnings=warnings,
        )


def _parameter_version(registry: ParameterRegistry, snapshot: HistoricalSnapshot) -> str:
    return registry.parameter_version_for(["ai_cycle_weights"], snapshot.decision_date)
