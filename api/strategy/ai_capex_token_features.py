from __future__ import annotations

from statistics import mean
from typing import Mapping

from api.domain.scoring.ai_capex_token_contracts import (
    AICapexTokenFallbackState,
    AICapexTokenFeatureSet,
    AICapexTokenRawSnapshot,
    CapexAccelerationDirection,
    TokenConsumptionDirection,
)


class AICapexTokenFeatureBuilder:
    def build(
        self,
        snapshot: AICapexTokenRawSnapshot,
        *,
        config: Mapping[str, object] | None = None,
    ) -> AICapexTokenFeatureSet:
        reason_codes: list[str] = []
        warnings: list[str] = []
        metrics = [*snapshot.token_sources_current, *snapshot.token_sources_previous, *snapshot.capex_series]
        data_quality = min((metric.quality_score for metric in metrics), default=0.0)
        if any(metric.missing_ratio > 0.0 or metric.is_stale for metric in metrics):
            data_quality = min(data_quality, 0.4)
            reason_codes.append("LOW_DATA_QUALITY_REVIEW_REQUIRED")

        token_current = sum(metric.value for metric in snapshot.token_sources_current)
        token_previous = sum(metric.value for metric in snapshot.token_sources_previous)
        capex_by_role = {metric.period_role: metric.value for metric in snapshot.capex_series}
        fallback_state: AICapexTokenFallbackState | None = None

        if token_previous <= 0:
            return _fallback(snapshot, data_quality, "TOKEN_PREVIOUS_INVALID_REVIEW_REQUIRED")
        if any(value < 0 for value in [token_current, token_previous, *capex_by_role.values()]):
            return _fallback(snapshot, data_quality, "NEGATIVE_TOTAL_REVIEW_REQUIRED")
        if not {"t", "t_minus_1", "t_minus_2"}.issubset(capex_by_role):
            return _fallback(snapshot, data_quality, "MISSING_CAPEX_PERIOD_REVIEW_REQUIRED")
        if capex_by_role["t_minus_1"] <= 0 or capex_by_role["t_minus_2"] <= 0:
            return _fallback(snapshot, data_quality, "CAPEX_PREVIOUS_INVALID_REVIEW_REQUIRED")

        delta_token_growth = token_current / token_previous - 1.0
        capex_growth_t = capex_by_role["t"] / capex_by_role["t_minus_1"] - 1.0
        capex_growth_t_minus_1 = capex_by_role["t_minus_1"] / capex_by_role["t_minus_2"] - 1.0
        capex_acceleration = capex_growth_t - capex_growth_t_minus_1

        if not _normalization_is_approved(config):
            fallback_state = AICapexTokenFallbackState.REVIEW_REQUIRED
            reason_codes.append("NORMALIZATION_PARAMETERS_REVIEW_REQUIRED")
            warnings.append("normalized_directional_scores_not_computed")

        return AICapexTokenFeatureSet(
            snapshot_id=snapshot.snapshot_id,
            as_of_date=snapshot.decision_date,
            token_consumption_change=delta_token_growth,
            capex_growth=capex_growth_t,
            capex_acceleration=capex_acceleration,
            token_direction=_token_direction(delta_token_growth),
            capex_direction=_capex_direction(capex_acceleration),
            data_quality=data_quality if data_quality <= 0.5 else mean(metric.quality_score for metric in metrics),
            fallback_state=fallback_state,
            reason_codes=tuple(reason_codes),
            warnings=tuple(warnings),
        )


def build_ai_capex_token_features(
    snapshot: AICapexTokenRawSnapshot,
    *,
    config: Mapping[str, object] | None = None,
) -> AICapexTokenFeatureSet:
    return AICapexTokenFeatureBuilder().build(snapshot, config=config)


def _token_direction(value: float) -> TokenConsumptionDirection:
    if value > 0:
        return TokenConsumptionDirection.EXPANDING
    if value < 0:
        return TokenConsumptionDirection.CONTRACTING
    return TokenConsumptionDirection.STABLE


def _capex_direction(value: float) -> CapexAccelerationDirection:
    if value > 0:
        return CapexAccelerationDirection.ACCELERATING
    if value < 0:
        return CapexAccelerationDirection.DECELERATING
    return CapexAccelerationDirection.STABLE


def _fallback(snapshot: AICapexTokenRawSnapshot, data_quality: float, reason_code: str) -> AICapexTokenFeatureSet:
    return AICapexTokenFeatureSet(
        snapshot_id=snapshot.snapshot_id,
        as_of_date=snapshot.decision_date,
        token_consumption_change=None,
        capex_growth=None,
        capex_acceleration=None,
        token_direction=TokenConsumptionDirection.STABLE,
        capex_direction=CapexAccelerationDirection.STABLE,
        data_quality=min(data_quality, 0.0),
        fallback_state=AICapexTokenFallbackState.REVIEW_REQUIRED,
        reason_codes=(reason_code,),
    )


def _normalization_is_approved(config: Mapping[str, object] | None) -> bool:
    if not config:
        return False
    metadata = (config.get("normalization_parameters") or {}).get("metadata") if isinstance(config.get("normalization_parameters"), Mapping) else None
    return bool(isinstance(metadata, Mapping) and metadata.get("approved") is True)
