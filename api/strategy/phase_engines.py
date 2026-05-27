from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class PhaseEngineError(ValueError):
    pass


@dataclass(frozen=True)
class MacroRegimeInput:
    as_of_date: date
    component_scores: dict[str, float | None]
    confidence: float = 1.0
    data_quality: float = 1.0
    parameter_version: str = "phase7_v1"
    model_version: str = "macro_regime_distribution_v1"


@dataclass(frozen=True)
class MacroRegimeComponentScore:
    component: str
    score: float
    confidence: float
    data_quality: float
    reason_codes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MacroRegimeResult:
    as_of_date: date
    regime_distribution: dict[str, float]
    dominant_regime: str
    dominant_regime_explanation_only: bool
    confidence: float
    data_quality: float
    component_scores: list[MacroRegimeComponentScore]
    reason_codes: list[str]
    warnings: list[str]
    parameter_version: str
    model_version: str


class MacroRegimeDistributionEngine:
    regimes = ("risk_on_growth", "neutral", "inflation_pressure", "recession_risk", "volatility_stress")

    def evaluate(self, macro_input: MacroRegimeInput) -> MacroRegimeResult:
        components: list[MacroRegimeComponentScore] = []
        warnings: list[str] = []
        contributions = {regime: 0.2 for regime in self.regimes}
        mapping = {
            "growth": {"risk_on_growth": 0.55, "neutral": 0.2},
            "inflation": {"inflation_pressure": 0.45, "neutral": 0.2},
            "credit": {"recession_risk": 0.35, "volatility_stress": 0.25},
            "volatility": {"volatility_stress": 0.5, "neutral": 0.1},
            "liquidity": {"recession_risk": 0.3, "risk_on_growth": 0.2},
        }
        valid_count = 0
        for component, raw_value in macro_input.component_scores.items():
            if raw_value is None:
                warnings.append(f"MISSING_MACRO_COMPONENT:{component}")
                components.append(MacroRegimeComponentScore(component, 0.5, 0.0, 0.0, ["REVIEW_REQUIRED"], ["MISSING_COMPONENT"]))
                continue
            score = _clamp(float(raw_value))
            valid_count += 1
            components.append(MacroRegimeComponentScore(component, score, macro_input.confidence, macro_input.data_quality, [f"MACRO_COMPONENT:{component}"]))
            for regime, weight in mapping.get(component, {"neutral": 0.3}).items():
                contributions[regime] += score * weight
        if valid_count == 0:
            warnings.extend(["ALL_MACRO_COMPONENTS_MISSING", "REVIEW_REQUIRED"])
            distribution = {regime: 1 / len(self.regimes) for regime in self.regimes}
            confidence = 0.0
        else:
            distribution = _normalize(contributions)
            concentration = max(distribution.values()) - min(distribution.values())
            confidence = _clamp((0.5 + concentration) * macro_input.confidence * macro_input.data_quality)
            if confidence < 0.4:
                warnings.append("LOW_MACRO_CONFIDENCE")
        dominant = max(distribution, key=lambda key: (distribution[key], key))
        return MacroRegimeResult(
            as_of_date=macro_input.as_of_date,
            regime_distribution=distribution,
            dominant_regime=dominant,
            dominant_regime_explanation_only=True,
            confidence=confidence,
            data_quality=macro_input.data_quality,
            component_scores=components,
            reason_codes=sorted({code for component in components for code in component.reason_codes}),
            warnings=warnings,
            parameter_version=macro_input.parameter_version,
            model_version=macro_input.model_version,
        )


@dataclass(frozen=True)
class SectorDefinition:
    sector_id: str
    enabled: bool
    feature_tags: list[str]
    asset_candidates: list[str]
    component_weights: dict[str, float]
    parameter_version: str = "phase8_v1"
    model_version: str = "sector_scoring_v1"

    def __post_init__(self) -> None:
        _require_text(self.sector_id, "sector_id")
        if not self.asset_candidates:
            raise PhaseEngineError("asset_candidates must be non-empty")
        if not self.component_weights:
            raise PhaseEngineError("component_weights must be non-empty")


@dataclass(frozen=True)
class SectorScoreInput:
    as_of_date: date
    sector_id: str
    macro_regime_distribution: dict[str, float]
    component_inputs: dict[str, float | None]
    confidence: float = 1.0
    data_quality: float = 1.0
    previous_score: float | None = None


@dataclass(frozen=True)
class SectorComponentScore:
    name: str
    score: float
    weight: float
    contribution: float
    reason_codes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SectorScoreResult:
    as_of_date: date
    sector_id: str
    total_score: float
    rank: int | None
    confidence: float
    data_quality: float
    component_scores: list[SectorComponentScore]
    asset_candidates: list[str]
    score_change: float | None
    reason_codes: list[str]
    warnings: list[str]
    parameter_version: str
    model_version: str


def load_sector_definitions(path: str | Path = PROJECT_ROOT / "config" / "sector_scoring.yaml") -> dict[str, SectorDefinition]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    output: dict[str, SectorDefinition] = {}
    for sector_id, raw in (data.get("sectors") or {}).items():
        output[sector_id] = SectorDefinition(
            sector_id=sector_id,
            enabled=bool(raw.get("enabled", True)),
            feature_tags=list(raw.get("feature_tags") or []),
            asset_candidates=list(raw.get("asset_candidates") or []),
            component_weights={key: float(value) for key, value in (raw.get("component_weights") or {}).items()},
            parameter_version=raw.get("parameter_version", "phase8_v1"),
            model_version=raw.get("model_version", "sector_scoring_v1"),
        )
    if not output:
        raise PhaseEngineError("no sectors configured")
    return output


class SectorScoringEngine:
    def __init__(self, definitions: dict[str, SectorDefinition]):
        self.definitions = definitions

    def score_sector(self, score_input: SectorScoreInput) -> SectorScoreResult:
        definition = self.definitions.get(score_input.sector_id)
        if definition is None or not definition.enabled:
            return SectorScoreResult(
                score_input.as_of_date,
                score_input.sector_id,
                0.5,
                None,
                0.0,
                0.0,
                [],
                [],
                None,
                ["REVIEW_REQUIRED"],
                ["UNKNOWN_OR_DISABLED_SECTOR"],
                "phase8_v1",
                "sector_scoring_v1",
            )
        components: list[SectorComponentScore] = []
        warnings: list[str] = []
        macro_fit = _macro_fit(score_input.macro_regime_distribution)
        inputs = {"macro_fit": macro_fit, **score_input.component_inputs}
        for name, weight in definition.component_weights.items():
            raw_score = inputs.get(name)
            if raw_score is None:
                warnings.append(f"MISSING_SECTOR_COMPONENT:{name}")
                score = 0.5
                component_warnings = ["MISSING_COMPONENT_REVIEW_REQUIRED"]
            else:
                score = _clamp(float(raw_score))
                component_warnings = []
            if name == "risk_penalty":
                score = 1.0 - score
            components.append(SectorComponentScore(name, score, weight, score * weight, [f"SECTOR_COMPONENT:{name}"], component_warnings))
        total_weight = sum(max(0.0, component.weight) for component in components)
        total = 0.5 if total_weight <= 0 else sum(component.contribution for component in components) / total_weight
        adjusted = _clamp(0.5 + (_clamp(total) - 0.5) * _clamp(score_input.confidence) * _clamp(score_input.data_quality))
        score_change = None if score_input.previous_score is None else adjusted - score_input.previous_score
        return SectorScoreResult(
            score_input.as_of_date,
            score_input.sector_id,
            adjusted,
            None,
            _clamp(score_input.confidence * (0.5 if warnings else 1.0)),
            score_input.data_quality,
            components,
            definition.asset_candidates,
            score_change,
            sorted({code for component in components for code in component.reason_codes}),
            warnings,
            definition.parameter_version,
            definition.model_version,
        )

    def rank(self, results: list[SectorScoreResult]) -> list[SectorScoreResult]:
        ordered = sorted(results, key=lambda item: (-item.total_score, item.sector_id))
        return [
            SectorScoreResult(
                result.as_of_date,
                result.sector_id,
                result.total_score,
                index + 1,
                result.confidence,
                result.data_quality,
                result.component_scores,
                result.asset_candidates,
                result.score_change,
                result.reason_codes,
                result.warnings,
                result.parameter_version,
                result.model_version,
            )
            for index, result in enumerate(ordered)
        ]


@dataclass(frozen=True)
class AssetRiskContribution:
    asset_id: str
    weight: float
    volatility_penalty: float = 0.0
    concentration_penalty: float = 0.0
    liquidity_penalty: float = 0.0
    drawdown_pressure: float = 0.0


@dataclass(frozen=True)
class AccountRiskBudget:
    account_id: str
    account_type: str
    risky_asset_exposure: float
    max_risky_asset_exposure: float
    remaining_capacity: float
    blocked: bool
    reason_codes: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class PortfolioRiskBudget:
    total_risky_exposure: float
    max_risky_exposure: float
    risk_budget_score: float
    asset_contributions: list[AssetRiskContribution]
    reason_codes: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class RiskBudgetInput:
    as_of_date: date
    account_id: str | None
    account_type: str | None
    holdings_weights: dict[str, float]
    risky_assets: set[str]
    asset_volatility: dict[str, float] = field(default_factory=dict)
    asset_liquidity: dict[str, float] = field(default_factory=dict)
    drawdown: float = 0.0
    data_quality: float = 1.0


@dataclass(frozen=True)
class RiskBudgetResult:
    as_of_date: date
    portfolio: PortfolioRiskBudget
    account: AccountRiskBudget
    blocked: bool
    risk_increase_allowed: bool
    reason_codes: list[str]
    warnings: list[str]
    parameter_version: str = "phase9_v1"
    model_version: str = "risk_budget_v1"


class RiskBudgetScoringEngine:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {
            "portfolio": {"max_risky_asset_exposure": 0.75, "max_single_asset_weight": 0.25},
            "accounts": {"GENERAL": {"max_risky_asset_exposure": 0.8}, "IRP": {"max_risky_asset_exposure": 0.7}},
        }

    def evaluate(self, risk_input: RiskBudgetInput) -> RiskBudgetResult:
        warnings: list[str] = []
        reason_codes: list[str] = []
        if not risk_input.account_id or not risk_input.account_type:
            warnings.append("MISSING_ACCOUNT_STATE")
            reason_codes.append("REVIEW_REQUIRED")
        risky_exposure = sum(weight for asset, weight in risk_input.holdings_weights.items() if asset in risk_input.risky_assets)
        account_limit = float((self.config.get("accounts", {}).get(risk_input.account_type or "") or {}).get("max_risky_asset_exposure", 0.0))
        portfolio_limit = float(self.config.get("portfolio", {}).get("max_risky_asset_exposure", 0.75))
        contributions = []
        for asset, weight in risk_input.holdings_weights.items():
            volatility_penalty = _clamp(risk_input.asset_volatility.get(asset, 0.0))
            concentration_penalty = _clamp(max(0.0, weight - float(self.config.get("portfolio", {}).get("max_single_asset_weight", 0.25))))
            liquidity_penalty = _clamp(1.0 - risk_input.asset_liquidity.get(asset, 1.0))
            contributions.append(AssetRiskContribution(asset, weight, volatility_penalty, concentration_penalty, liquidity_penalty, _clamp(abs(risk_input.drawdown))))
        penalty = _clamp(sum(c.volatility_penalty + c.concentration_penalty + c.liquidity_penalty + c.drawdown_pressure for c in contributions) / max(len(contributions) * 4, 1))
        risk_budget_score = _clamp((1.0 - penalty) * risk_input.data_quality)
        if risk_input.data_quality < 0.7:
            warnings.append("LOW_DATA_QUALITY_BLOCKS_RISK_INCREASE")
        blocked = bool(warnings) or risky_exposure > account_limit or risky_exposure > portfolio_limit
        if risky_exposure > account_limit:
            reason_codes.append("ACCOUNT_RISK_LIMIT_BREACH")
        if risky_exposure > portfolio_limit:
            reason_codes.append("PORTFOLIO_RISK_LIMIT_BREACH")
        account = AccountRiskBudget(
            risk_input.account_id or "UNKNOWN",
            risk_input.account_type or "UNKNOWN",
            _clamp(risky_exposure),
            _clamp(account_limit),
            max(0.0, account_limit - risky_exposure),
            blocked,
            reason_codes,
            warnings,
        )
        portfolio = PortfolioRiskBudget(_clamp(risky_exposure), _clamp(portfolio_limit), risk_budget_score, contributions, reason_codes, warnings)
        return RiskBudgetResult(risk_input.as_of_date, portfolio, account, blocked, not blocked, sorted(set(reason_codes)), sorted(set(warnings)))


@dataclass(frozen=True)
class TargetRange:
    asset_id: str
    min_weight: float
    base_weight: float
    max_weight: float
    max_change: float

    def __post_init__(self) -> None:
        if not 0 <= self.min_weight <= self.base_weight <= self.max_weight <= 1:
            raise PhaseEngineError("target range must satisfy min <= base <= max within [0,1]")


@dataclass(frozen=True)
class AllocationInput:
    as_of_date: date
    asset_id: str
    target_range: TargetRange
    previous_target: float
    macro_distribution: dict[str, float]
    sector_score: float
    sector_confidence: float
    risk_budget_score: float
    constraint_blocked: bool = False


@dataclass(frozen=True)
class AllocationAdjustment:
    macro_adjustment: float
    sector_adjustment: float
    conviction_adjustment: float
    risk_penalty_adjustment: float
    concentration_penalty: float
    cost_tax_adjustment: float


@dataclass(frozen=True)
class TargetAllocationResult:
    as_of_date: date
    asset_id: str
    target_range: TargetRange
    current_target_weight: float
    adjustments: AllocationAdjustment
    blocked: bool
    reason_codes: list[str]
    warnings: list[str]
    parameter_version: str = "phase10_v1"
    model_version: str = "allocation_v1"


class ScoreBasedAllocationEngine:
    def calculate(self, allocation_input: AllocationInput) -> TargetAllocationResult:
        if allocation_input.constraint_blocked:
            return TargetAllocationResult(
                allocation_input.as_of_date,
                allocation_input.asset_id,
                allocation_input.target_range,
                0.0,
                AllocationAdjustment(0, 0, 0, 0, 0, 0),
                True,
                ["HARD_CONSTRAINT_BLOCKED"],
                ["TARGET_ZEROED_BY_CONSTRAINT"],
            )
        macro_adjustment = (allocation_input.macro_distribution.get("risk_on_growth", 0.0) - allocation_input.macro_distribution.get("volatility_stress", 0.0)) * 0.05
        sector_adjustment = (allocation_input.sector_score - 0.5) * 0.2 * allocation_input.sector_confidence
        risk_penalty = (1.0 - allocation_input.risk_budget_score) * 0.1
        preliminary = allocation_input.target_range.base_weight + macro_adjustment + sector_adjustment - risk_penalty
        bounded = max(allocation_input.target_range.min_weight, min(allocation_input.target_range.max_weight, preliminary))
        delta = max(-allocation_input.target_range.max_change, min(allocation_input.target_range.max_change, bounded - allocation_input.previous_target))
        current_target = _clamp(allocation_input.previous_target + delta)
        return TargetAllocationResult(
            allocation_input.as_of_date,
            allocation_input.asset_id,
            allocation_input.target_range,
            current_target,
            AllocationAdjustment(macro_adjustment, sector_adjustment, sector_adjustment, -risk_penalty, 0.0, 0.0),
            False,
            ["SCORE_BASED_GRADUAL_TARGET"],
            [],
        )

    def normalize(self, results: list[TargetAllocationResult], cash_asset_id: str = "CASH_KRW") -> list[TargetAllocationResult]:
        active = [result for result in results if not result.blocked and result.asset_id != cash_asset_id]
        total = sum(result.current_target_weight for result in active)
        residual = max(0.0, 1.0 - min(total, 1.0))
        normalized: list[TargetAllocationResult] = []
        scale = 1.0 if total <= 1.0 else 1.0 / total
        for result in results:
            if result.asset_id == cash_asset_id:
                normalized.append(_replace_target(result, residual, ["CASH_RESIDUAL_TARGET"]))
            elif result.blocked:
                normalized.append(result)
            else:
                normalized.append(_replace_target(result, result.current_target_weight * scale, result.reason_codes))
        if cash_asset_id not in {result.asset_id for result in normalized}:
            cash_range = TargetRange(cash_asset_id, 0.0, residual, 1.0, 1.0)
            normalized.append(TargetAllocationResult(results[0].as_of_date if results else date.today(), cash_asset_id, cash_range, residual, AllocationAdjustment(0, 0, 0, 0, 0, 0), False, ["CASH_RESIDUAL_TARGET"], []))
        return normalized


@dataclass(frozen=True)
class RebalanceInput:
    as_of_date: date
    asset_id: str
    current_weight: float
    target_weight: float
    target_min: float
    target_max: float
    score_change: float
    risk_pressure: float
    cash_available: float
    turnover_penalty: float
    data_quality: float = 1.0


@dataclass(frozen=True)
class RebalanceComponentScores:
    drift: float
    conviction_change: float
    risk_pressure: float
    cash_availability: float
    cost_efficiency: float
    tax_efficiency: float
    turnover_penalty: float


@dataclass(frozen=True)
class RebalanceIntensity:
    score: float
    band: str


@dataclass(frozen=True)
class RebalanceActionCandidate:
    asset_id: str
    action: str
    estimated_weight_change: float
    reason_codes: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class RebalanceResult:
    as_of_date: date
    asset_id: str
    components: RebalanceComponentScores
    intensity: RebalanceIntensity
    action_candidate: RebalanceActionCandidate
    warnings: list[str]
    reason_codes: list[str]
    parameter_version: str = "phase11_v1"
    model_version: str = "rebalancing_v1"


class RebalancingIntensityEngine:
    def evaluate(self, rebalance_input: RebalanceInput) -> RebalanceResult:
        overweight = max(0.0, rebalance_input.current_weight - rebalance_input.target_max)
        underweight = max(0.0, rebalance_input.target_min - rebalance_input.current_weight)
        drift = _clamp(max(overweight, underweight) * 5)
        conviction = _clamp(0.5 + rebalance_input.score_change)
        components = RebalanceComponentScores(
            drift=drift,
            conviction_change=conviction,
            risk_pressure=_clamp(rebalance_input.risk_pressure),
            cash_availability=_clamp(rebalance_input.cash_available),
            cost_efficiency=0.8,
            tax_efficiency=0.8,
            turnover_penalty=_clamp(rebalance_input.turnover_penalty),
        )
        intensity_score = _clamp(drift * 0.35 + components.risk_pressure * 0.35 + components.cash_availability * 0.1 + components.cost_efficiency * 0.1 - components.turnover_penalty * 0.2)
        warnings: list[str] = []
        reason_codes: list[str] = ["REBALANCE_SCORE_FLOW"]
        if rebalance_input.data_quality < 0.7:
            warnings.append("LOW_DATA_QUALITY_REVIEW_REQUIRED")
        action = "NO_ACTION"
        if warnings:
            action = "REVIEW_REQUIRED"
        elif components.risk_pressure >= 0.8:
            action = "RISK_REDUCE_ONLY"
        elif overweight > 0 and rebalance_input.score_change > 0:
            action = "HOLD_OVERWEIGHT_WINNER"
            reason_codes.append("OVERWEIGHT_WINNER_SCORE_IMPROVING")
        elif overweight > 0 and rebalance_input.score_change < -0.05:
            action = "PARTIAL_REDUCTION_CANDIDATE"
        elif underweight > 0 and rebalance_input.cash_available > 0:
            action = "BUY_CANDIDATE"
        elif underweight > 0:
            action = "ADJUST_WITH_NEW_CASH"
        band = "high" if intensity_score >= 0.7 else "medium" if intensity_score >= 0.3 else "low"
        change = _clamp(abs(rebalance_input.target_weight - rebalance_input.current_weight))
        candidate = RebalanceActionCandidate(rebalance_input.asset_id, action, change, reason_codes, warnings)
        return RebalanceResult(rebalance_input.as_of_date, rebalance_input.asset_id, components, RebalanceIntensity(intensity_score, band), candidate, warnings, reason_codes)


def _macro_fit(distribution: dict[str, float]) -> float:
    return _clamp(0.5 + distribution.get("risk_on_growth", 0.0) * 0.4 - distribution.get("volatility_stress", 0.0) * 0.3 - distribution.get("recession_risk", 0.0) * 0.2)


def _replace_target(result: TargetAllocationResult, target: float, reason_codes: list[str]) -> TargetAllocationResult:
    return TargetAllocationResult(
        result.as_of_date,
        result.asset_id,
        result.target_range,
        _clamp(target),
        result.adjustments,
        result.blocked,
        reason_codes,
        result.warnings,
        result.parameter_version,
        result.model_version,
    )


def _normalize(values: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, value) for value in values.values())
    if total <= 0:
        return {key: 1 / len(values) for key in values}
    return {key: max(0.0, value) / total for key, value in values.items()}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PhaseEngineError(f"{field_name} is required")
