from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from api.domain.scoring.ai_capex_token_contracts import AICapexTokenScenarioDistribution
from api.score_pipeline.contracts import PipelineContractError, clamp_ratio


SECTOR_IDS = (
    "bigtech_platform",
    "power_equipment",
    "semiconductor_hbm",
    "cash_short_duration",
    "inverse_hedge_diagnostic",
)


@dataclass(frozen=True)
class AdaptiveSectorDiagnostic:
    sector_id: str
    component_score: float
    component_contribution: float
    contribution_cap: float
    confidence: float
    data_quality: float
    stability: float
    valuation_dampener: float
    macro_stress_dampener: float
    turnover_dampener: float
    diagnostic_only: bool
    user_review_required: bool
    reason_codes: tuple[str, ...]
    warnings: tuple[str, ...]
    parameter_version: str
    model_version: str

    def __post_init__(self) -> None:
        if self.sector_id not in SECTOR_IDS:
            raise PipelineContractError("unsupported adaptive sector diagnostic")
        for field_name in (
            "component_score",
            "component_contribution",
            "contribution_cap",
            "confidence",
            "data_quality",
            "stability",
            "valuation_dampener",
            "macro_stress_dampener",
            "turnover_dampener",
        ):
            value = float(getattr(self, field_name))
            if not 0.0 <= value <= 1.0:
                raise PipelineContractError(f"{field_name} must be between 0 and 1")
        if self.component_contribution > self.contribution_cap:
            raise PipelineContractError("component_contribution cannot exceed contribution_cap")
        if self.diagnostic_only is not True:
            raise PipelineContractError("adaptive sector diagnostic must stay diagnostic_only")
        if not self.parameter_version:
            raise PipelineContractError("parameter_version is required")
        if not self.model_version:
            raise PipelineContractError("model_version is required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_adaptive_sector_diagnostics(
    distribution: AICapexTokenScenarioDistribution,
    sector_metrics: Mapping[str, Mapping[str, float]],
    *,
    config: Mapping[str, object],
    macro_stress: float,
    stability: float,
    turnover_pressure: float,
) -> tuple[AdaptiveSectorDiagnostic, ...]:
    cap = _config_ratio(config, "max_component_contribution")
    valuation_penalty = _config_ratio(config, "valuation_burden_penalty")
    macro_stress_attenuation = _config_ratio(config, "macro_stress_attenuation")
    turnover_penalty = _config_ratio(config, "turnover_penalty")
    data_quality = clamp_ratio(distribution.data_quality)
    confidence = clamp_ratio(distribution.confidence)
    common = {
        "contribution_cap": cap,
        "confidence": confidence,
        "data_quality": data_quality,
        "stability": clamp_ratio(stability),
        "macro_stress_dampener": clamp_ratio(1.0 - clamp_ratio(macro_stress) * macro_stress_attenuation),
        "turnover_dampener": clamp_ratio(1.0 - clamp_ratio(turnover_pressure) * turnover_penalty),
        "parameter_version": distribution.parameter_version,
        "model_version": "ai_capex_token_adaptive_sector_diagnostics_v1",
    }
    diagnostics = [
        _risk_component(
            "bigtech_platform",
            _bigtech_raw(distribution, sector_metrics.get("bigtech_platform", {})),
            sector_metrics.get("bigtech_platform", {}),
            common=common,
            valuation_penalty=valuation_penalty,
            reasons=("bigtech_platform_adaptive_diagnostic",),
        ),
        _risk_component(
            "power_equipment",
            _power_raw(distribution, sector_metrics.get("power_equipment", {})),
            sector_metrics.get("power_equipment", {}),
            common=common,
            valuation_penalty=valuation_penalty,
            reasons=("power_equipment_adaptive_diagnostic",),
        ),
        _risk_component(
            "semiconductor_hbm",
            _hbm_raw(distribution, sector_metrics.get("semiconductor_hbm", {})),
            sector_metrics.get("semiconductor_hbm", {}),
            common=common,
            valuation_penalty=valuation_penalty,
            reasons=("semiconductor_hbm_adaptive_diagnostic",),
        ),
        _cash_component(distribution, common, macro_stress=macro_stress),
        _inverse_component(distribution, common),
    ]
    return tuple(diagnostics)


def _risk_component(
    sector_id: str,
    raw_score: tuple[float, tuple[str, ...]],
    metrics: Mapping[str, float],
    *,
    common: Mapping[str, Any],
    valuation_penalty: float,
    reasons: tuple[str, ...],
) -> AdaptiveSectorDiagnostic:
    raw, raw_reasons = raw_score
    missing_count = sum(1 for reason in raw_reasons if reason.startswith("missing_"))
    confidence = clamp_ratio(common["confidence"] * (0.6 if missing_count else 1.0))
    data_quality = clamp_ratio(common["data_quality"] * (0.7 if missing_count else 1.0))
    valuation_burden = _metric(metrics, "valuation_burden_score", default=0.5)[0]
    valuation_dampener = clamp_ratio(1.0 - valuation_burden * valuation_penalty)
    dampened = raw * confidence * data_quality * common["stability"] * valuation_dampener * common["macro_stress_dampener"] * common["turnover_dampener"]
    contribution = min(common["contribution_cap"], dampened * common["contribution_cap"])
    adjusted_common = {**common, "confidence": confidence, "data_quality": data_quality}
    return AdaptiveSectorDiagnostic(
        sector_id=sector_id,
        component_score=clamp_ratio(raw),
        component_contribution=contribution,
        valuation_dampener=valuation_dampener,
        diagnostic_only=True,
        user_review_required=bool(missing_count),
        reason_codes=(*reasons, *raw_reasons, "market_state_dampening_applied"),
        warnings=("missing_sector_metric_review_required",) if missing_count else (),
        **adjusted_common,
    )


def _cash_component(
    distribution: AICapexTokenScenarioDistribution,
    common: Mapping[str, Any],
    *,
    macro_stress: float,
) -> AdaptiveSectorDiagnostic:
    raw = clamp_ratio(
        (
            distribution.probabilities["S7"]
            + distribution.probabilities["S8"]
            + (1.0 - distribution.data_quality)
            + clamp_ratio(macro_stress)
        )
        / 4.0
    )
    contribution = min(common["contribution_cap"], raw * common["contribution_cap"])
    return AdaptiveSectorDiagnostic(
        sector_id="cash_short_duration",
        component_score=raw,
        component_contribution=contribution,
        valuation_dampener=1.0,
        diagnostic_only=True,
        user_review_required=False,
        reason_codes=("cash_short_duration_defensive_diagnostic",),
        warnings=(),
        **common,
    )


def _inverse_component(
    distribution: AICapexTokenScenarioDistribution,
    common: Mapping[str, Any],
) -> AdaptiveSectorDiagnostic:
    raw = clamp_ratio(distribution.probabilities["S7"])
    contribution = min(common["contribution_cap"], raw * common["contribution_cap"])
    return AdaptiveSectorDiagnostic(
        sector_id="inverse_hedge_diagnostic",
        component_score=raw,
        component_contribution=contribution,
        valuation_dampener=1.0,
        diagnostic_only=True,
        user_review_required=True,
        reason_codes=("inverse_hedge_diagnostic_only", "requires_existing_hedge_policy"),
        warnings=("inverse_hedge_cannot_be_order_candidate",),
        **common,
    )


def _bigtech_raw(
    distribution: AICapexTokenScenarioDistribution,
    metrics: Mapping[str, float],
) -> tuple[float, tuple[str, ...]]:
    monetization, reasons_a = _metric(metrics, "ai_monetization_score", default=0.0)
    fcf, reasons_b = _metric(metrics, "fcf_margin_improvement_score", default=0.0)
    capex_burden, reasons_c = _metric(metrics, "capex_burden_score", default=0.5)
    score = (
        distribution.probabilities["S2"]
        + distribution.probabilities["S3"]
        + monetization
        + fcf
        + (1.0 - capex_burden)
    ) / 5.0
    return clamp_ratio(score), (*reasons_a, *reasons_b, *reasons_c)


def _power_raw(
    distribution: AICapexTokenScenarioDistribution,
    metrics: Mapping[str, float],
) -> tuple[float, tuple[str, ...]]:
    backlog, reasons_a = _metric(metrics, "backlog_growth_score", default=0.0)
    asp, reasons_b = _metric(metrics, "asp_growth_score", default=0.0)
    score = (distribution.probabilities["S1"] + backlog + asp) / 3.0
    return clamp_ratio(score), (*reasons_a, *reasons_b)


def _hbm_raw(
    distribution: AICapexTokenScenarioDistribution,
    metrics: Mapping[str, float],
) -> tuple[float, tuple[str, ...]]:
    asp, reasons_a = _metric(metrics, "hbm_asp_growth_score", default=0.0)
    supply, reasons_b = _metric(metrics, "hbm_supply_growth_score", default=0.0)
    inventory, reasons_c = _metric(metrics, "hbm_inventory_risk_score", default=0.5)
    score = (distribution.probabilities["S1"] + asp + supply + (1.0 - inventory)) / 4.0
    return clamp_ratio(score), (*reasons_a, *reasons_b, *reasons_c)


def _metric(metrics: Mapping[str, float], key: str, *, default: float) -> tuple[float, tuple[str, ...]]:
    if key not in metrics:
        return clamp_ratio(default), (f"missing_{key}_review_required",)
    return clamp_ratio(float(metrics[key])), ()


def _config_ratio(config: Mapping[str, object], name: str) -> float:
    value = config.get(name)
    if value is None:
        raise PipelineContractError(f"{name} is required")
    return clamp_ratio(float(value))
