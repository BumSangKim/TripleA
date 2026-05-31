from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from api.score_pipeline.contracts import (
    BottleneckScoreBreakdown,
    DataQualityMetadata,
    DecisionWarning,
    FeatureOutput,
    PipelineContractError,
    ReasonCode,
)
from api.score_pipeline.data_quality import HistoricalSnapshot
from api.score_pipeline.parameters import ParameterRegistry
from api.score_pipeline.plugins.capex_common import clamp, conservative_score_on_missing, weighted_average


STRUCTURAL_MOAT_COMPONENTS = (
    "switching_cost",
    "regulatory_lock_in",
    "recurring_revenue",
    "installed_base",
    "customer_diversification",
    "workflow_penetration",
)
DEMAND_MOMENTUM_COMPONENTS = (
    "segment_growth",
    "order_growth",
    "backlog_growth",
    "book_to_bill",
    "consumables_growth",
    "inventory_normalization",
)
FINANCIAL_QUALITY_COMPONENTS = (
    "gross_margin",
    "ebitda_margin",
    "fcf_margin",
    "roic",
    "balance_sheet",
    "margin_stability",
)
RISK_PENALTY_COMPONENTS = (
    "one_off_demand",
    "customer_inventory_risk",
    "order_deceleration",
    "valuation_overheat",
    "overcapacity",
    "funding_risk",
    "guidance_cut",
    "geopolitical_risk",
)
CLINICAL_EVENT_TAGS = {
    "clinical_event_biotech",
    "single_pipeline_biotech",
    "clinical_event_risk",
    "single_pipeline_risk",
    "binary_event_risk",
}


@dataclass(frozen=True)
class BioCapexBottleneckPlugin:
    feature_id: str = "score:bio_capex_bottleneck"
    feature_name: str = "Bio/Pharma CapEx Bottleneck"

    def compute(
        self,
        snapshot: HistoricalSnapshot,
        registry: ParameterRegistry,
        *,
        asset_id: str = "bio_capex_bottleneck",
        asset_tags: set[str] | None = None,
    ) -> FeatureOutput:
        breakdown = self.compute_breakdown(snapshot, registry, asset_id=asset_id, asset_tags=asset_tags)
        return FeatureOutput(
            feature_id=self.feature_id,
            feature_name=self.feature_name,
            entity_id=asset_id,
            entity_type="asset",
            raw_value=breakdown.final_score,
            normalized_value=breakdown.final_score,
            confidence=breakdown.confidence,
            data_quality=_quality_from_breakdown(snapshot, breakdown),
            as_of_date=snapshot.decision_date,
            source="bio_capex_bottleneck",
            parameter_version=breakdown.parameter_version,
            model_version=breakdown.model_version,
            reason_codes=breakdown.reason_codes,
            warnings=breakdown.warnings,
        )

    def compute_breakdown(
        self,
        snapshot: HistoricalSnapshot,
        registry: ParameterRegistry,
        *,
        asset_id: str = "bio_capex_bottleneck",
        asset_tags: set[str] | None = None,
    ) -> BottleneckScoreBreakdown:
        warnings: list[DecisionWarning] = list(snapshot.warnings)
        reason_codes = [ReasonCode("BIO_CAPEX_BOTTLENECK_COMPUTED", "score")]
        asset_tags = asset_tags or set()
        if not is_core_anchor_allowed(asset_tags):
            reason_codes.append(ReasonCode("BIO_CAPEX_CORE_ANCHOR_BLOCKED", "risk", "clinical event or single-pipeline tag"))
            warnings.append(
                DecisionWarning(
                    "BIO_CAPEX_CLINICAL_EVENT_OBSERVATION_ONLY",
                    "WARNING",
                    "score",
                    "clinical-event-sensitive assets are observation-only",
                )
            )

        final_lookup = registry.get("final_score_weights", as_of_date=snapshot.decision_date, expected_type=dict)
        structural_lookup = registry.get("structural_moat_weights", as_of_date=snapshot.decision_date, expected_type=dict)
        demand_lookup = registry.get("demand_momentum_weights", as_of_date=snapshot.decision_date, expected_type=dict)
        quality_lookup = registry.get("financial_quality_weights", as_of_date=snapshot.decision_date, expected_type=dict)
        risk_lookup = registry.get("risk_penalty_weights", as_of_date=snapshot.decision_date, expected_type=dict)
        lookups = [final_lookup, structural_lookup, demand_lookup, quality_lookup, risk_lookup]
        for lookup in lookups:
            warnings.extend(lookup.warnings)
        if any(lookup.value is None for lookup in lookups):
            reason_codes.append(ReasonCode("BIO_CAPEX_DATA_MISSING", "score", "missing bottleneck weights"))
            fallback = conservative_score_on_missing()
            return BottleneckScoreBreakdown(
                asset_id=asset_id,
                structural_moat=0.5,
                demand_momentum=0.5,
                financial_quality=0.5,
                risk_penalty=0.5,
                final_score=float(fallback["score"]),
                confidence=float(fallback["confidence"]),
                data_quality=0.0,
                as_of_date=snapshot.decision_date,
                parameter_version=final_lookup.version_ref.version,
                model_version="bio_capex_bottleneck_plugin_v0",
                reason_codes=reason_codes,
                warnings=warnings,
            )

        values, future_keys = _snapshot_values(snapshot)
        for key in future_keys:
            warnings.append(DecisionWarning("BIO_CAPEX_FUTURE_DATA_REJECTED", "BLOCKER", "score", key))
        missing_ratio = _missing_ratio(values)
        if missing_ratio > 0:
            reason_codes.append(ReasonCode("BIO_CAPEX_DATA_MISSING", "score"))
            warnings.append(DecisionWarning("BIO_CAPEX_MISSING_COMPONENT", "WARNING", "score", "missing component input"))
        data_quality = clamp(1.0 - missing_ratio)
        structural_moat = weighted_average(_pick(values, STRUCTURAL_MOAT_COMPONENTS), structural_lookup.value)
        demand_momentum = weighted_average(_pick(values, DEMAND_MOMENTUM_COMPONENTS), demand_lookup.value)
        financial_quality = weighted_average(_pick(values, FINANCIAL_QUALITY_COMPONENTS), quality_lookup.value)
        risk_penalty = weighted_average(_pick(values, RISK_PENALTY_COMPONENTS), risk_lookup.value)
        final_weights = final_lookup.value
        final_score = clamp(
            float(final_weights["structural_moat"]) * structural_moat
            + float(final_weights["demand_momentum"]) * demand_momentum
            + float(final_weights["financial_quality"]) * financial_quality
            - float(final_weights["risk_penalty_multiplier"]) * risk_penalty
        )
        return BottleneckScoreBreakdown(
            asset_id=asset_id,
            structural_moat=structural_moat,
            demand_momentum=demand_momentum,
            financial_quality=financial_quality,
            risk_penalty=risk_penalty,
            final_score=final_score,
            confidence=data_quality,
            data_quality=data_quality,
            as_of_date=snapshot.decision_date,
            parameter_version=final_lookup.version_ref.version,
            model_version="bio_capex_bottleneck_plugin_v0",
            reason_codes=reason_codes,
            warnings=warnings,
        )


def is_core_anchor_allowed(asset_tags: set[str]) -> bool:
    return not bool(asset_tags & CLINICAL_EVENT_TAGS)


def _snapshot_values(snapshot: HistoricalSnapshot) -> tuple[dict[str, float | None], list[str]]:
    required = (
        *STRUCTURAL_MOAT_COMPONENTS,
        *DEMAND_MOMENTUM_COMPONENTS,
        *FINANCIAL_QUALITY_COMPONENTS,
        *RISK_PENALTY_COMPONENTS,
    )
    values: dict[str, float | None] = {}
    future_keys: list[str] = []
    for key in required:
        try:
            point = snapshot.get_available(key)
        except PipelineContractError:
            point = None
            future_keys.append(key)
        values[key] = None if point is None else point.value
    return values, future_keys


def _pick(values: dict[str, float | None], keys: tuple[str, ...]) -> dict[str, float | None]:
    return {key: values.get(key) for key in keys}


def _missing_ratio(values: dict[str, float | None]) -> float:
    if not values:
        return 1.0
    return sum(1 for value in values.values() if value is None) / len(values)


def _quality_from_breakdown(snapshot: HistoricalSnapshot, breakdown: BottleneckScoreBreakdown) -> DataQualityMetadata:
    updated_at = datetime.combine(snapshot.decision_date, datetime.min.time(), tzinfo=UTC)
    return DataQualityMetadata(
        source="bio_capex_bottleneck",
        as_of_date=snapshot.decision_date,
        updated_at=updated_at,
        quality_score=breakdown.data_quality,
        missing_ratio=1.0 - breakdown.data_quality,
        is_stale=False,
        warnings=breakdown.warnings,
    )
