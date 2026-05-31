from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from api.features.backtests.sector_component_models import CONSERVATIVE_FALLBACK_STATES


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "backtests" / "sector_component_backtest.yaml"
REQUIRED_KEYS = {
    "parameter_version",
    "model_version",
    "enabled_components",
    "component_weight_grid",
    "rebalance_frequency",
    "decision_lag_days",
    "transaction_cost_bps",
    "tax_assumption_enabled",
    "stress_periods",
    "required_metrics",
    "fallback_policy",
}
KNOWN_COMPONENTS = {"trade", "demand", "supply", "relative_strength", "quality", "valuation", "momentum"}
ALLOWED_REBALANCE_FREQUENCIES = {"weekly", "monthly", "quarterly"}


class SectorComponentConfigError(ValueError):
    pass


@dataclass(frozen=True)
class SectorComponentConfigWarning:
    code: str
    message: str
    fallback_state: str = "REVIEW_REQUIRED"

    def __post_init__(self) -> None:
        if self.fallback_state not in CONSERVATIVE_FALLBACK_STATES:
            raise ValueError("fallback_state must be conservative")


@dataclass(frozen=True)
class SectorComponentWeightSet:
    parameter_set_id: str
    weights: dict[str, float]


@dataclass(frozen=True)
class SectorComponentStressPeriod:
    name: str
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise SectorComponentConfigError(f"{self.name}: stress period start_date must not be after end_date")


@dataclass(frozen=True)
class SectorComponentBacktestConfig:
    parameter_version: str
    model_version: str
    enabled_components: tuple[str, ...]
    component_weight_grid: tuple[SectorComponentWeightSet, ...]
    rebalance_frequency: str
    decision_lag_days: int
    transaction_cost_bps: float
    tax_assumption_enabled: bool
    stress_periods: tuple[SectorComponentStressPeriod, ...]
    required_metrics: tuple[str, ...]
    fallback_policy: str
    validation_warnings: tuple[SectorComponentConfigWarning, ...] = field(default_factory=tuple)


def load_sector_component_backtest_config(path: str | Path = DEFAULT_CONFIG_PATH) -> SectorComponentBacktestConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return parse_sector_component_backtest_config(raw)


def parse_sector_component_backtest_config(raw: dict[str, Any]) -> SectorComponentBacktestConfig:
    missing = sorted(REQUIRED_KEYS - set(raw))
    if missing:
        raise SectorComponentConfigError(f"missing required config keys: {', '.join(missing)}")

    parameter_version = _required_text(raw["parameter_version"], "parameter_version")
    model_version = _required_text(raw["model_version"], "model_version")
    enabled_components = tuple(_required_text(value, "enabled_components") for value in _required_list(raw["enabled_components"], "enabled_components"))
    if not enabled_components:
        raise SectorComponentConfigError("enabled_components must not be empty")

    warnings: list[SectorComponentConfigWarning] = []
    unknown_enabled = sorted(set(enabled_components) - KNOWN_COMPONENTS)
    if unknown_enabled:
        warnings.append(
            SectorComponentConfigWarning(
                code="UNKNOWN_COMPONENT_REVIEW_REQUIRED",
                message=f"unknown components require review: {', '.join(unknown_enabled)}",
            )
        )

    component_weight_grid = tuple(_parse_weight_set(item, enabled_components) for item in _required_list(raw["component_weight_grid"], "component_weight_grid"))
    if not component_weight_grid:
        raise SectorComponentConfigError("component_weight_grid must not be empty")

    rebalance_frequency = _required_text(raw["rebalance_frequency"], "rebalance_frequency").lower()
    if rebalance_frequency not in ALLOWED_REBALANCE_FREQUENCIES:
        raise SectorComponentConfigError("rebalance_frequency must be weekly, monthly, or quarterly")

    decision_lag_days = int(raw["decision_lag_days"])
    if decision_lag_days < 0:
        raise SectorComponentConfigError("decision_lag_days must be non-negative")
    transaction_cost_bps = float(raw["transaction_cost_bps"])
    if transaction_cost_bps < 0:
        raise SectorComponentConfigError("transaction_cost_bps must be non-negative")
    fallback_policy = _required_text(raw["fallback_policy"], "fallback_policy")
    if fallback_policy not in CONSERVATIVE_FALLBACK_STATES:
        raise SectorComponentConfigError("fallback_policy must be conservative")

    return SectorComponentBacktestConfig(
        parameter_version=parameter_version,
        model_version=model_version,
        enabled_components=enabled_components,
        component_weight_grid=component_weight_grid,
        rebalance_frequency=rebalance_frequency,
        decision_lag_days=decision_lag_days,
        transaction_cost_bps=transaction_cost_bps,
        tax_assumption_enabled=bool(raw["tax_assumption_enabled"]),
        stress_periods=tuple(_parse_stress_period(item) for item in _required_list(raw["stress_periods"], "stress_periods")),
        required_metrics=tuple(_required_text(value, "required_metrics") for value in _required_list(raw["required_metrics"], "required_metrics")),
        fallback_policy=fallback_policy,
        validation_warnings=tuple(warnings),
    )


def _parse_weight_set(raw: dict[str, Any], enabled_components: tuple[str, ...]) -> SectorComponentWeightSet:
    parameter_set_id = _required_text(raw.get("parameter_set_id"), "parameter_set_id")
    weights_raw = raw.get("weights")
    if not isinstance(weights_raw, dict) or not weights_raw:
        raise SectorComponentConfigError(f"{parameter_set_id}: weights must be a non-empty mapping")
    unknown_weights = sorted(set(weights_raw) - set(enabled_components))
    if unknown_weights:
        raise SectorComponentConfigError(f"{parameter_set_id}: weights reference disabled components: {', '.join(unknown_weights)}")
    missing_weights = sorted(set(enabled_components) - set(weights_raw))
    if missing_weights:
        raise SectorComponentConfigError(f"{parameter_set_id}: missing weights for: {', '.join(missing_weights)}")
    weights = {str(component): float(value) for component, value in weights_raw.items()}
    if any(value < 0 for value in weights.values()):
        raise SectorComponentConfigError(f"{parameter_set_id}: weights must be non-negative")
    total = sum(weights.values())
    if abs(total - 1.0) > 0.000001:
        raise SectorComponentConfigError(f"{parameter_set_id}: weights must sum to 1.0")
    return SectorComponentWeightSet(parameter_set_id=parameter_set_id, weights=weights)


def _parse_stress_period(raw: dict[str, Any]) -> SectorComponentStressPeriod:
    return SectorComponentStressPeriod(
        name=_required_text(raw.get("name"), "stress_period.name"),
        start_date=date.fromisoformat(_required_text(raw.get("start_date"), "stress_period.start_date")),
        end_date=date.fromisoformat(_required_text(raw.get("end_date"), "stress_period.end_date")),
    )


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SectorComponentConfigError(f"{field_name} must be non-empty text")
    return value.strip()


def _required_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise SectorComponentConfigError(f"{field_name} must be a list")
    return value

