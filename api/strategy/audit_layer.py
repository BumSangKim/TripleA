from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any


class AuditLayerError(ValueError):
    pass


REASON_CODE_CATALOG: dict[str, str] = {
    "DATA_QUALITY_LOW": "data_quality",
    "MISSING_HISTORICAL_SNAPSHOT_REVIEW_REQUIRED": "data_quality",
    "MACRO_COMPONENT:growth": "macro_regime",
    "LOW_MACRO_CONFIDENCE": "macro_regime",
    "SECTOR_COMPONENT:macro_fit": "sector_score",
    "ACCOUNT_RISK_LIMIT_BREACH": "risk_budget",
    "PORTFOLIO_RISK_LIMIT_BREACH": "risk_budget",
    "SCORE_BASED_GRADUAL_TARGET": "allocation",
    "CASH_RESIDUAL_TARGET": "allocation",
    "REBALANCE_SCORE_FLOW": "rebalancing",
    "OVERWEIGHT_WINNER_SCORE_IMPROVING": "rebalancing",
    "HARD_CONSTRAINT_BLOCKED": "account_constraint",
    "ORDER_CANDIDATE_VALIDATED": "order_candidate",
    "REVIEW_REQUIRED": "fallback",
}
WARNING_SEVERITIES = {"INFO", "WARNING", "ERROR", "BLOCKER"}


@dataclass(frozen=True)
class AuditWarning:
    code: str
    source_module: str
    severity: str = "WARNING"
    message: str = ""

    def __post_init__(self) -> None:
        if self.severity not in WARNING_SEVERITIES:
            raise AuditLayerError("unsupported warning severity")


@dataclass(frozen=True)
class DecisionTrace:
    macro_scores: dict[str, Any] = field(default_factory=dict)
    sector_scores: dict[str, Any] = field(default_factory=dict)
    risk_budget_scores: dict[str, Any] = field(default_factory=dict)
    target_weights: dict[str, float] = field(default_factory=dict)
    current_weights: dict[str, float] = field(default_factory=dict)
    rebalance_scores: dict[str, Any] = field(default_factory=dict)
    account_constraints: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionLogEntry:
    decision_id: str
    date: date
    data_snapshot_id: str
    parameter_version: str
    model_version: str
    decision_result: str
    adjustment_intensity: float
    trace: DecisionTrace
    reason_codes: list[str] = field(default_factory=list)
    warnings: list[AuditWarning] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in ("decision_id", "data_snapshot_id", "parameter_version", "model_version", "decision_result"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise AuditLayerError(f"{field_name} is required")
        if not 0.0 <= self.adjustment_intensity <= 1.0:
            raise AuditLayerError("adjustment_intensity must be between 0 and 1")


@dataclass(frozen=True)
class DecisionLog:
    log_id: str
    entries: list[DecisionLogEntry]
    created_by: str = "system"

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str, sort_keys=True)


@dataclass(frozen=True)
class Explanation:
    decision_id: str
    decision_result: str
    reason_codes: list[str]
    warnings: list[AuditWarning]
    trace: DecisionTrace | None
    summary: str
    available: bool = True


def validate_reason_catalog(catalog: dict[str, str] = REASON_CODE_CATALOG) -> None:
    if len(catalog) != len(set(catalog)):
        raise AuditLayerError("duplicate reason codes detected")
    required = {
        "data_quality",
        "macro_regime",
        "sector_score",
        "risk_budget",
        "allocation",
        "rebalancing",
        "account_constraint",
        "order_candidate",
        "fallback",
    }
    missing = required - set(catalog.values())
    if missing:
        raise AuditLayerError(f"missing reason categories: {sorted(missing)}")


def aggregate_warnings(*groups: list[AuditWarning]) -> list[AuditWarning]:
    by_key: dict[tuple[str, str], AuditWarning] = {}
    severity_rank = {"INFO": 0, "WARNING": 1, "ERROR": 2, "BLOCKER": 3}
    for group in groups:
        for warning in group:
            key = (warning.code, warning.source_module)
            existing = by_key.get(key)
            if existing is None or severity_rank[warning.severity] > severity_rank[existing.severity]:
                by_key[key] = warning
    return list(by_key.values())


class BacktestReportGenerator:
    def generate_json(self, result: Any) -> dict[str, Any]:
        metrics = getattr(result, "metrics", {}) or {}
        warnings = list(getattr(result, "warnings", []) or [])
        required_metrics = ["cagr", "mdd", "annualized_volatility", "sharpe", "sortino", "calmar", "turnover", "cost_adjusted_return", "tax_adjusted_return"]
        metric_block = {
            metric: metrics.get(metric)
            for metric in required_metrics
        }
        for metric, value in metric_block.items():
            if value is None:
                warnings.append(f"METRIC_UNAVAILABLE:{metric}")
        return {
            "parameter_version": getattr(result, "parameter_version", "unknown"),
            "model_version": getattr(result, "model_version", "unknown"),
            "metrics": metric_block,
            "stress_period_performance": metrics.get("stress_period_performance"),
            "regime_by_regime_performance": metrics.get("regime_by_regime_performance"),
            "warnings": sorted(set(warnings)),
            "claim": "Backtest report is historical review output, not a future performance claim.",
        }

    def generate_markdown(self, result: Any) -> str:
        report = self.generate_json(result)
        lines = [
            "# Backtest Report",
            f"- parameter_version: {report['parameter_version']}",
            f"- model_version: {report['model_version']}",
            "## Metrics",
        ]
        for key, value in report["metrics"].items():
            lines.append(f"- {key}: {'unavailable' if value is None else value}")
        if report["warnings"]:
            lines.append("## Warnings")
            lines.extend(f"- {warning}" for warning in report["warnings"])
        return "\n".join(lines) + "\n"


class ExplanationService:
    def __init__(self, decision_log: DecisionLog):
        self.decision_log = decision_log

    def explain(self, decision_id: str) -> Explanation:
        for entry in self.decision_log.entries:
            if entry.decision_id == decision_id:
                return Explanation(
                    decision_id=entry.decision_id,
                    decision_result=entry.decision_result,
                    reason_codes=entry.reason_codes,
                    warnings=entry.warnings,
                    trace=entry.trace,
                    summary=f"{entry.decision_result} was produced from recorded reason codes: {', '.join(entry.reason_codes) or 'none'}.",
                    available=True,
                )
        return Explanation(decision_id, "UNAVAILABLE", [], [], None, "Decision log entry is unavailable.", False)


def mask_account_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= 4:
        return "****"
    return f"****{value[-4:]}"
