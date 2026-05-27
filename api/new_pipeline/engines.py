from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from api.new_pipeline.contracts import (
    AllocationTargetRange,
    CandidateAction,
    ConservativeAction,
    ConstraintResult,
    DecisionWarning,
    MacroRegimeDistribution,
    ReasonCode,
    RebalancingDecision,
    RiskBudgetOutput,
    ScoreOutput,
    SectorScoreOutput,
    clamp_ratio,
)
from api.new_pipeline.parameters import ParameterRegistry


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SECTOR_PATH = PROJECT_ROOT / "config" / "parameters" / "sectors.yaml"


@dataclass(frozen=True)
class SectorDefinition:
    sector_id: str
    enabled: bool
    component_weights: dict[str, float]


class MacroRegimeEngine:
    regimes = ("risk_on_growth", "neutral", "inflation_pressure", "recession_risk", "volatility_stress")

    def evaluate(self, scores: list[ScoreOutput], registry: ParameterRegistry, *, as_of_date: date) -> MacroRegimeDistribution:
        parameter_version = registry.parameter_version_for(["score_weights"], as_of_date)
        if not scores:
            distribution = {regime: 1.0 / len(self.regimes) for regime in self.regimes}
            return MacroRegimeDistribution(
                as_of_date,
                distribution,
                "neutral",
                True,
                0.0,
                0.0,
                [ReasonCode("MACRO_REVIEW_REQUIRED", "macro")],
                [DecisionWarning("MISSING_MACRO_SCORES", "WARNING", "macro", "neutral distribution used")],
                parameter_version,
                "new_pipeline_macro_v1",
            )
        raw = {regime: 0.2 for regime in self.regimes}
        for score in scores:
            key = score.score_id.lower()
            value = score.score
            if "growth" in key or "momentum" in key:
                raw["risk_on_growth"] += value * 0.35
                raw["neutral"] += (1 - abs(value - 0.5)) * 0.10
            if "inflation" in key or "commodity" in key:
                raw["inflation_pressure"] += value * 0.30
            if "credit" in key or "drawdown" in key:
                raw["recession_risk"] += value * 0.30
            if "volatility" in key or "stress" in key or "risk" in key:
                raw["volatility_stress"] += value * 0.35
        distribution = _normalize(raw)
        dominant = max(distribution, key=lambda name: (distribution[name], name))
        confidence = clamp_ratio(sum(score.confidence for score in scores) / len(scores))
        data_quality = clamp_ratio(sum(score.data_quality for score in scores) / len(scores))
        warnings = []
        if confidence < 0.5 or data_quality < 0.7:
            warnings.append(DecisionWarning("LOW_MACRO_CONFIDENCE_OR_QUALITY", "WARNING", "macro", "downstream should limit risk increase"))
        return MacroRegimeDistribution(
            as_of_date,
            distribution,
            dominant,
            True,
            confidence,
            data_quality,
            [ReasonCode("MACRO_DISTRIBUTION_SCORE_FLOW", "macro")],
            warnings,
            parameter_version,
            "new_pipeline_macro_v1",
        )


def load_sector_definitions(path: str | Path = DEFAULT_SECTOR_PATH) -> dict[str, SectorDefinition]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return {
        sector_id: SectorDefinition(
            sector_id=sector_id,
            enabled=bool(item.get("enabled", True)),
            component_weights={name: float(value) for name, value in (item.get("component_weights") or {}).items()},
        )
        for sector_id, item in (raw.get("sectors") or {}).items()
    }


class SectorScoringEngine:
    def __init__(self, definitions: dict[str, SectorDefinition] | None = None):
        self.definitions = definitions or load_sector_definitions()

    def score(
        self,
        *,
        sector_id: str,
        macro: MacroRegimeDistribution,
        components: dict[str, float | None],
        as_of_date: date,
        registry: ParameterRegistry,
        previous_score: float | None = None,
    ) -> SectorScoreOutput:
        definition = self.definitions.get(sector_id)
        if definition is None or not definition.enabled:
            return _sector_fallback(sector_id, as_of_date, registry, "UNKNOWN_OR_DISABLED_SECTOR")
        weighted: dict[str, float] = {}
        warnings: list[DecisionWarning] = []
        macro_fit = clamp_ratio(0.5 + macro.distribution.get("risk_on_growth", 0.0) * 0.25 - macro.distribution.get("volatility_stress", 0.0) * 0.20)
        values = {"macro_fit": macro_fit, "data_quality": macro.data_quality, **components}
        for name, weight in definition.component_weights.items():
            raw_value = values.get(name)
            if raw_value is None:
                warnings.append(DecisionWarning("MISSING_SECTOR_COMPONENT", "WARNING", "sector", name))
                value = 0.5
            else:
                value = clamp_ratio(float(raw_value))
            if name == "risk_penalty":
                value = 1.0 - value
            weighted[name] = value * max(weight, 0.0)
        total_weight = sum(max(weight, 0.0) for weight in definition.component_weights.values())
        total = 0.5 if total_weight <= 0 else sum(weighted.values()) / total_weight
        confidence = clamp_ratio(macro.confidence * (0.75 if warnings else 1.0))
        adjusted = clamp_ratio(0.5 + (total - 0.5) * confidence * macro.data_quality)
        prev = adjusted if previous_score is None else previous_score
        return SectorScoreOutput(
            sector_id=sector_id,
            total_score=adjusted,
            component_scores={name: clamp_ratio(value / max(definition.component_weights[name], 1e-9)) for name, value in weighted.items()},
            score=adjusted,
            previous_score=previous_score,
            score_change=adjusted - prev,
            confidence=confidence,
            data_quality=macro.data_quality,
            stability=clamp_ratio(1 - abs(adjusted - prev)),
            adjustment_intensity=clamp_ratio(abs(adjusted - 0.5) * confidence),
            as_of_date=as_of_date,
            parameter_version=registry.parameter_version_for(["score_weights"], as_of_date),
            model_version="new_pipeline_sector_v1",
            reason_codes=[ReasonCode("SECTOR_SCORE_DECOMPOSED", "sector")],
            warnings=warnings,
        )


class RiskBudgetEngine:
    def evaluate(
        self,
        *,
        account_type: str,
        current_weights: dict[str, float],
        risky_assets: set[str],
        volatility: float,
        drawdown: float,
        data_quality: float,
        registry: ParameterRegistry,
        as_of_date: date,
    ) -> RiskBudgetOutput:
        limits = registry.get("account_risk_limits", as_of_date=as_of_date, expected_type=dict)
        warnings = list(limits.warnings)
        account_limits = limits.value or {}
        account = account_limits.get(account_type)
        if not account:
            constraint = ConstraintResult(False, True, [ReasonCode("INVALID_ACCOUNT_TYPE", "constraint")], warnings, ConservativeAction.REVIEW_REQUIRED)
        else:
            max_risky = float(account.get("max_risky_asset_weight", 0.0))
            risky_weight = sum(weight for asset, weight in current_weights.items() if asset in risky_assets)
            blocked = risky_weight > max_risky or data_quality < 0.5
            reasons = []
            if risky_weight > max_risky:
                reasons.append(ReasonCode("RISKY_ASSET_LIMIT_BLOCKED", "constraint"))
            if data_quality < 0.5:
                warnings.append(DecisionWarning("LOW_DATA_QUALITY_BLOCKS_RISK_INCREASE", "WARNING", "risk", "quality too low"))
            constraint = ConstraintResult(not blocked, blocked, reasons, warnings, ConservativeAction.REVIEW_REQUIRED if blocked else None)
        risk_penalty = clamp_ratio(volatility * 0.5 + abs(drawdown) * 0.5 + (1 - data_quality) * 0.5)
        score = clamp_ratio(1.0 - risk_penalty)
        return RiskBudgetOutput(
            portfolio_risk_score=score,
            account_risk_score=0.0 if constraint.blocked else score,
            risk_penalty=risk_penalty,
            risk_capacity=0.0 if constraint.blocked else score,
            constraint_result=constraint,
            score=score,
            previous_score=None,
            score_change=0.0,
            confidence=clamp_ratio(data_quality),
            data_quality=clamp_ratio(data_quality),
            stability=1.0,
            adjustment_intensity=clamp_ratio(1 - score),
            as_of_date=as_of_date,
            parameter_version=registry.parameter_version_for(["account_risk_limits"], as_of_date),
            model_version="new_pipeline_risk_v1",
            reason_codes=[ReasonCode("RISK_BUDGET_SCORE_FLOW", "risk"), *constraint.reason_codes],
            warnings=warnings,
        )


class AllocationEngine:
    def allocate(
        self,
        *,
        asset_id: str,
        sector_score: SectorScoreOutput,
        macro: MacroRegimeDistribution,
        risk: RiskBudgetOutput,
        previous_target: float,
        registry: ParameterRegistry,
    ) -> AllocationTargetRange:
        ranges = registry.get("asset_weight_ranges", as_of_date=sector_score.as_of_date, expected_type=dict)
        change_limit = registry.get("target_change_limit", as_of_date=sector_score.as_of_date, expected_type=(int, float))
        default_range = (ranges.value or {}).get("default", {"min": 0.0, "base": 0.0, "max": 0.0})
        min_weight = float(default_range["min"])
        base_weight = float(default_range["base"])
        max_weight = float(default_range["max"])
        macro_adjust = (macro.distribution.get("risk_on_growth", 0.0) - macro.distribution.get("volatility_stress", 0.0)) * 0.05
        sector_adjust = (sector_score.total_score - 0.5) * 0.20 * sector_score.confidence
        risk_adjust = -risk.risk_penalty * 0.10
        preliminary = base_weight + macro_adjust + sector_adjust + risk_adjust
        if risk.constraint_result.blocked:
            final = 0.0
            warnings = [*risk.warnings, DecisionWarning("HARD_CONSTRAINT_ZERO_TARGET", "BLOCKER", "allocation", asset_id)]
        else:
            bounded = max(min_weight, min(max_weight, preliminary))
            limit = float(change_limit.value) if change_limit.value is not None else 0.02
            delta = max(-limit, min(limit, bounded - previous_target))
            final = max(min_weight, min(max_weight, previous_target + delta))
            warnings = [*ranges.warnings, *change_limit.warnings]
        return AllocationTargetRange(
            asset_id=asset_id,
            min_weight=min_weight,
            base_weight=base_weight,
            max_weight=max_weight,
            current_target=clamp_ratio(final),
            previous_target=clamp_ratio(previous_target),
            confidence=min(sector_score.confidence, risk.confidence, macro.confidence),
            data_quality=min(sector_score.data_quality, risk.data_quality, macro.data_quality),
            as_of_date=sector_score.as_of_date,
            parameter_version=registry.parameter_version_for(["asset_weight_ranges", "target_change_limit"], sector_score.as_of_date),
            model_version="new_pipeline_allocation_v1",
            reason_codes=[ReasonCode("ALLOCATION_SCORE_FLOW", "allocation"), *risk.reason_codes],
            warnings=warnings,
        )


class RebalancingEngine:
    def decide(
        self,
        *,
        target: AllocationTargetRange,
        current_weight: float,
        sector_score: SectorScoreOutput,
        risk: RiskBudgetOutput,
        cash_available_score: float,
        turnover_penalty: float,
        is_satellite: bool = False,
    ) -> RebalancingDecision:
        drift = abs(target.current_target - current_weight)
        intensity = clamp_ratio(drift * 3 + risk.adjustment_intensity * 0.4 + cash_available_score * 0.1 - turnover_penalty * 0.3)
        reasons = [ReasonCode("REBALANCING_INTENSITY_SCORE_FLOW", "rebalancing")]
        warnings: list[DecisionWarning] = []
        overweight = current_weight > target.max_weight
        if target.data_quality < 0.6 or sector_score.data_quality < 0.6:
            action = ConservativeAction.REVIEW_REQUIRED
            warnings.append(DecisionWarning("LOW_DATA_QUALITY_REVIEW_REQUIRED", "WARNING", "rebalancing", target.asset_id))
        elif risk.constraint_result.blocked:
            action = ConservativeAction.RISK_REDUCE_ONLY
        elif is_satellite and overweight and sector_score.score_change >= 0:
            action = "STOP_NEW_BUYS" if sector_score.score_change == 0 else "LIMITED_INCREASE"
            reasons.append(ReasonCode("OVERWEIGHT_WINNER_NOT_MECHANICALLY_SOLD", "rebalancing"))
        elif overweight and sector_score.score_change < 0:
            action = CandidateAction.REDUCE
        elif sector_score.score_change > 0 and risk.risk_capacity > 0:
            action = CandidateAction.BUY
        else:
            action = CandidateAction.HOLD
        return RebalancingDecision(
            asset_id=target.asset_id,
            action=action,
            intensity=intensity,
            target_weight=target.current_target,
            current_weight=clamp_ratio(current_weight),
            score=sector_score.score,
            previous_score=sector_score.previous_score,
            score_change=sector_score.score_change,
            confidence=min(target.confidence, sector_score.confidence, risk.confidence),
            data_quality=min(target.data_quality, sector_score.data_quality, risk.data_quality),
            stability=sector_score.stability,
            adjustment_intensity=intensity,
            as_of_date=target.as_of_date,
            parameter_version=target.parameter_version,
            model_version="new_pipeline_rebalancing_v1",
            reason_codes=reasons,
            warnings=warnings,
        )


def _sector_fallback(sector_id: str, as_of_date: date, registry: ParameterRegistry, code: str) -> SectorScoreOutput:
    return SectorScoreOutput(
        sector_id=sector_id,
        total_score=0.5,
        component_scores={},
        score=0.5,
        previous_score=None,
        score_change=0.0,
        confidence=0.0,
        data_quality=0.0,
        stability=1.0,
        adjustment_intensity=0.0,
        as_of_date=as_of_date,
        parameter_version=registry.parameter_version_for(["score_weights"], as_of_date),
        model_version="new_pipeline_sector_v1",
        reason_codes=[ReasonCode("SECTOR_REVIEW_REQUIRED", "sector")],
        warnings=[DecisionWarning(code, "WARNING", "sector", sector_id)],
    )


def _normalize(raw: dict[str, float]) -> dict[str, float]:
    total = sum(max(value, 0.0) for value in raw.values())
    if total <= 0:
        return {key: 1.0 / len(raw) for key in raw}
    return {key: max(value, 0.0) / total for key, value in raw.items()}
