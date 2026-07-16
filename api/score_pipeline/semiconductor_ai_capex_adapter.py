from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Mapping

from api.plugin_boundary.contracts import FeatureValue
from api.score_pipeline.contracts import ConservativeAction, PipelineContractError, clamp_ratio


@dataclass(frozen=True)
class SemiconductorAICapexFeatureSnapshot:
    snapshot_id: str
    as_of_date: datetime
    features: tuple[FeatureValue, ...]
    confidence: float
    data_quality: float
    diagnostic_only: bool
    allocation_contribution: float
    parameter_version: str
    model_version: str
    fallback_state: str | None = None
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.diagnostic_only is not True:
            raise PipelineContractError("AI Capex semiconductor adapter must remain diagnostic_only")
        if self.allocation_contribution != 0.0:
            raise PipelineContractError("AI Capex semiconductor adapter cannot contribute to allocation")
        if self.fallback_state is not None and self.fallback_state not in ConservativeAction.values():
            raise PipelineContractError("fallback_state must be conservative")


class SemiconductorAICapexShadowAdapter:
    """Projects existing diagnostic evidence into feature inputs without activating it."""

    def adapt(self, report: Mapping[str, Any], *, period_id: str) -> SemiconductorAICapexFeatureSnapshot:
        mode = report.get("mode") or {}
        result = report.get("diagnostic_result") or {}
        if mode.get("diagnostic_only") is not True or mode.get("production_enabled") is not False:
            raise PipelineContractError("source report is not a diagnostic-only shadow report")
        if result.get("allocation_contribution") != 0.0:
            raise PipelineContractError("source report allocation contribution must remain zero")
        period = _find_period(report.get("periods") or (), period_id)
        as_of_date = datetime.fromisoformat(str(period["as_of_date"]))
        available_at = datetime.combine(as_of_date.date(), time.max, tzinfo=as_of_date.tzinfo)
        parameter_version = _required_text(period, "parameter_version")
        model_version = _required_text(period, "model_version")
        confidence = clamp_ratio(float((period.get("market_state_dampeners") or {}).get("confidence", 0.0)))
        data_quality = clamp_ratio(float(period.get("data_quality_by_period", 0.0)))
        inputs = period.get("adaptive_normalized_features") or {}
        features: list[FeatureValue] = []
        missing: list[str] = []
        for source_key, feature_id in (
            ("token_delta", "semiconductor.demand.ai_capex_demand_pressure"),
            ("capex_acceleration", "semiconductor.demand.ai_capex_capex_momentum"),
        ):
            value = inputs.get(source_key)
            if value is None:
                missing.append(source_key)
            features.append(
                FeatureValue(
                    feature_id=feature_id,
                    entity_type="universe",
                    entity_id="SEMICONDUCTOR_ACTIVE_OVERLAY",
                    feature_value=None if value is None else float(value),
                    unit="normalized_ratio",
                    as_of_date=as_of_date.date(),
                    available_at=available_at,
                    source_dataset_ids=[str(report.get("report_version") or "ai_capex_token_shadow_report")],
                    source_plugin_ids=["ai_capex_token_shadow"],
                    calculation_method=f"existing_shadow_output:{source_key}",
                    feature_version="semiconductor_ai_capex_shadow_adapter_v1",
                    parameter_version=parameter_version,
                    data_quality=0.0 if value is None else data_quality,
                    missing_ratio=1.0 if value is None else 0.0,
                    is_stale=False,
                    warnings=["SEMICONDUCTOR_AI_CAPEX_FIELD_UNAVAILABLE"] if value is None else ["SEMICONDUCTOR_AI_CAPEX_DIAGNOSTIC_ONLY"],
                    reason_codes=["SEMICONDUCTOR_AI_CAPEX_REVIEW_REQUIRED"] if value is None else ["SEMICONDUCTOR_AI_CAPEX_ADAPTED_DIAGNOSTIC_ONLY"],
                    metadata={
                        "source_period_id": period_id,
                        "source_model_version": model_version,
                        "diagnostic_only": True,
                        "allocation_contribution": 0.0,
                    },
                )
            )
        return SemiconductorAICapexFeatureSnapshot(
            snapshot_id=f"{report.get('report_version', 'ai_capex_token_shadow')}:{period_id}",
            as_of_date=as_of_date,
            features=tuple(features),
            confidence=0.0 if missing else confidence,
            data_quality=0.0 if missing else data_quality,
            diagnostic_only=True,
            allocation_contribution=0.0,
            parameter_version=parameter_version,
            model_version=model_version,
            fallback_state=ConservativeAction.REVIEW_REQUIRED if missing else None,
            reason_codes=("SEMICONDUCTOR_AI_CAPEX_MISSING_FIELD",) if missing else ("SEMICONDUCTOR_AI_CAPEX_DIAGNOSTIC_ONLY",),
        )


def _find_period(periods: object, period_id: str) -> Mapping[str, Any]:
    for period in periods if isinstance(periods, list) else ():
        if isinstance(period, Mapping) and period.get("period_id") == period_id:
            return period
    raise PipelineContractError("requested AI Capex shadow period is unavailable")


def _required_text(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise PipelineContractError(f"AI Capex shadow period missing {field}")
    return value
