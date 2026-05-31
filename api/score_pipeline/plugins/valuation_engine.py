from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from api.score_pipeline.contracts import DecisionWarning, ReasonCode, ValuationResult
from api.score_pipeline.plugins.capex_common import clamp, safe_ratio


@dataclass(frozen=True)
class PERBounds:
    min_per: float
    max_per: float

    def __post_init__(self) -> None:
        if self.min_per <= 0 or self.max_per <= 0:
            raise ValueError("PER bounds must be positive")
        if self.min_per > self.max_per:
            raise ValueError("min_per must not exceed max_per")


@dataclass(frozen=True)
class ValuationEngine:
    parameter_version: str = "capex_valuation_v0"
    model_version: str = "capex_valuation_engine_v0"

    def evaluate(
        self,
        *,
        asset_id: str,
        as_of_date: date,
        forward_eps: float | None,
        midcycle_eps: float | None,
        base_per: float | None,
        last_price: float | None,
        macro_multiplier: float | None,
        per_bounds: PERBounds,
        confidence: float = 1.0,
        data_quality: float = 1.0,
    ) -> ValuationResult:
        warnings: list[DecisionWarning] = []
        reason_codes = [ReasonCode("VALUATION_COMPUTED", "valuation")]
        if _missing_or_non_positive(forward_eps) or _missing_or_non_positive(midcycle_eps):
            reason_codes.append(ReasonCode("VALUATION_MISSING_EPS", "valuation"))
            warnings.append(DecisionWarning("VALUATION_UNAVAILABLE", "WARNING", "valuation", "missing or non-positive EPS"))
            return _unavailable(
                asset_id=asset_id,
                as_of_date=as_of_date,
                forward_eps=forward_eps,
                midcycle_eps=midcycle_eps,
                base_per=base_per,
                last_price=last_price,
                macro_multiplier=macro_multiplier,
                confidence=0.0,
                data_quality=data_quality,
                reason_codes=[*reason_codes, ReasonCode("VALUATION_UNAVAILABLE", "valuation")],
                warnings=warnings,
                parameter_version=self.parameter_version,
                model_version=self.model_version,
            )
        if _missing_or_non_positive(base_per) or _missing_or_non_positive(last_price) or macro_multiplier is None:
            reason_codes.append(ReasonCode("VALUATION_UNAVAILABLE", "valuation"))
            warnings.append(DecisionWarning("VALUATION_UNAVAILABLE", "WARNING", "valuation", "missing core valuation input"))
            return _unavailable(
                asset_id=asset_id,
                as_of_date=as_of_date,
                forward_eps=forward_eps,
                midcycle_eps=midcycle_eps,
                base_per=base_per,
                last_price=last_price,
                macro_multiplier=macro_multiplier,
                confidence=0.0,
                data_quality=data_quality,
                reason_codes=reason_codes,
                warnings=warnings,
                parameter_version=self.parameter_version,
                model_version=self.model_version,
            )

        eps_persistence = clamp(safe_ratio(forward_eps, midcycle_eps))
        target_per = clamp_target_per(float(base_per) * (0.75 + 0.5 * eps_persistence), per_bounds)
        macro = max(0.0, float(macro_multiplier))
        if macro < 1.0:
            reason_codes.append(ReasonCode("VALUATION_MACRO_PENALTY", "valuation"))
            warnings.append(DecisionWarning("VALUATION_MACRO_PENALTY", "INFO", "valuation", f"macro_multiplier={macro:.4f}"))
        fair_value = float(midcycle_eps) * target_per * macro
        fair_value_ratio = safe_ratio(fair_value, last_price)
        return ValuationResult(
            asset_id=asset_id,
            forward_eps=float(forward_eps),
            midcycle_eps=float(midcycle_eps),
            eps_persistence=eps_persistence,
            base_per=float(base_per),
            target_per=target_per,
            macro_multiplier=macro,
            fair_value=fair_value,
            last_price=float(last_price),
            fair_value_ratio=fair_value_ratio,
            confidence=clamp(confidence),
            data_quality=clamp(data_quality),
            as_of_date=as_of_date,
            parameter_version=self.parameter_version,
            model_version=self.model_version,
            reason_codes=reason_codes,
            warnings=warnings,
        )


def clamp_target_per(raw_target_per: float, per_bounds: PERBounds) -> float:
    return max(per_bounds.min_per, min(per_bounds.max_per, float(raw_target_per)))


def _missing_or_non_positive(value: float | None) -> bool:
    return value is None or float(value) <= 0


def _unavailable(
    *,
    asset_id: str,
    as_of_date: date,
    forward_eps: float | None,
    midcycle_eps: float | None,
    base_per: float | None,
    last_price: float | None,
    macro_multiplier: float | None,
    confidence: float,
    data_quality: float,
    reason_codes: list[ReasonCode],
    warnings: list[DecisionWarning],
    parameter_version: str,
    model_version: str,
) -> ValuationResult:
    return ValuationResult(
        asset_id=asset_id,
        forward_eps=forward_eps,
        midcycle_eps=midcycle_eps,
        eps_persistence=None,
        base_per=base_per,
        target_per=None,
        macro_multiplier=macro_multiplier,
        fair_value=None,
        last_price=last_price,
        fair_value_ratio=None,
        confidence=clamp(confidence),
        data_quality=clamp(data_quality),
        as_of_date=as_of_date,
        parameter_version=parameter_version,
        model_version=model_version,
        reason_codes=reason_codes,
        warnings=warnings,
    )
