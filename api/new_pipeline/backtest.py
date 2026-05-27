from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable

from api.new_pipeline.contracts import DecisionLogRecord, DecisionWarning
from api.new_pipeline.data_quality import HistoricalSnapshot
from api.new_pipeline.parameters import ParameterRegistry


@dataclass(frozen=True)
class PipelineBacktestConfig:
    start_date: date
    end_date: date
    frequency: str
    initial_value: float
    parameter_version: str

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        if self.initial_value <= 0:
            raise ValueError("initial_value must be positive")


@dataclass(frozen=True)
class PortfolioState:
    cash: float
    weights: dict[str, float]
    value: float


@dataclass(frozen=True)
class PipelineBacktestResult:
    equity_curve: list[tuple[date, float]]
    decision_logs: list[DecisionLogRecord]
    metrics: dict[str, float | None]
    warnings: list[DecisionWarning] = field(default_factory=list)
    parameter_version: str = "new_pipeline_v1"
    model_version: str = "new_pipeline_backtest_v1"


class SimulationClock:
    def dates(self, config: PipelineBacktestConfig) -> list[date]:
        current = config.start_date
        output: list[date] = []
        while current <= config.end_date:
            output.append(current)
            current = _advance(current, config.frequency)
        if output[-1] != config.end_date:
            output.append(config.end_date)
        return output


class PipelineBacktestRunner:
    def __init__(self, registry: ParameterRegistry):
        self.registry = registry

    def run(
        self,
        config: PipelineBacktestConfig,
        snapshots: list[HistoricalSnapshot],
        pipeline: Callable[[HistoricalSnapshot, PortfolioState, ParameterRegistry], DecisionLogRecord],
    ) -> PipelineBacktestResult:
        by_date = {snapshot.decision_date: snapshot for snapshot in snapshots}
        state = PortfolioState(config.initial_value, {}, config.initial_value)
        equity_curve: list[tuple[date, float]] = []
        logs: list[DecisionLogRecord] = []
        warnings: list[DecisionWarning] = []
        for decision_date in SimulationClock().dates(config):
            snapshot = by_date.get(decision_date)
            if snapshot is None:
                warnings.append(DecisionWarning("MISSING_BACKTEST_SNAPSHOT", "WARNING", "backtest", decision_date.isoformat()))
                equity_curve.append((decision_date, state.value))
                continue
            if snapshot.warnings:
                warnings.extend(snapshot.warnings)
            log = pipeline(snapshot, state, self.registry)
            logs.append(log)
            turnover = sum(abs(log.target_weights.get(asset, 0.0) - state.weights.get(asset, 0.0)) for asset in set(log.target_weights) | set(state.weights))
            cost_bps = self.registry.get("transaction_cost_bps", as_of_date=decision_date, expected_type=(int, float)).value or 0.0
            cost = state.value * turnover * float(cost_bps) / 10_000.0
            state = PortfolioState(max(0.0, state.cash - cost), dict(log.target_weights), max(0.0, state.value - cost))
            equity_curve.append((decision_date, state.value))
        metrics = calculate_metrics(equity_curve, logs)
        return PipelineBacktestResult(equity_curve, logs, metrics, warnings, config.parameter_version)


def calculate_metrics(equity_curve: list[tuple[date, float]], logs: list[DecisionLogRecord]) -> dict[str, float | None]:
    if len(equity_curve) < 2:
        return _empty_metrics()
    values = [value for _, value in equity_curve]
    returns = [values[i] / values[i - 1] - 1 for i in range(1, len(values)) if values[i - 1] > 0]
    total_return = values[-1] / values[0] - 1 if values[0] > 0 else None
    elapsed_years = max((equity_curve[-1][0] - equity_curve[0][0]).days / 365.25, 1 / 365.25)
    cagr = (values[-1] / values[0]) ** (1 / elapsed_years) - 1 if values[0] > 0 else None
    mdd = _max_drawdown(values)
    vol = _stddev(returns) * math.sqrt(252) if len(returns) > 1 else 0.0
    sharpe = None if vol == 0 else (sum(returns) / len(returns)) * 252 / vol
    downside = [value for value in returns if value < 0]
    downside_vol = _stddev(downside) * math.sqrt(252) if len(downside) > 1 else 0.0
    sortino = None if downside_vol == 0 else (sum(returns) / len(returns)) * 252 / downside_vol
    calmar = None if not mdd else (cagr or 0.0) / abs(mdd)
    turnover = 0.0
    previous: dict[str, float] = {}
    for log in logs:
        turnover += sum(abs(log.target_weights.get(asset, 0.0) - previous.get(asset, 0.0)) for asset in set(log.target_weights) | set(previous)) / 2
        previous = dict(log.target_weights)
    return {
        "total_return": total_return,
        "cagr": cagr,
        "mdd": mdd,
        "annualized_volatility": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "turnover": turnover,
        "cost_adjusted_return": total_return,
        "regime_by_regime_performance": None,
        "contribution_analysis": None,
        "stress_period_performance": None,
        "parameter_sensitivity": None,
    }


def _advance(current: date, frequency: str) -> date:
    if frequency == "daily":
        return current + timedelta(days=1)
    if frequency == "weekly":
        return current + timedelta(days=7)
    return _advance_month(current)


def _advance_month(current: date) -> date:
    month = current.month + 1
    year = current.year
    if month > 12:
        month = 1
        year += 1
    return date(year, month, min(current.day, 28))


def _max_drawdown(values: list[float]) -> float:
    peak = values[0]
    drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            drawdown = min(drawdown, value / peak - 1)
    return drawdown


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = sum(values) / len(values)
    return math.sqrt(sum((value - avg) ** 2 for value in values) / (len(values) - 1))


def _empty_metrics() -> dict[str, float | None]:
    return {
        "total_return": None,
        "cagr": None,
        "mdd": None,
        "annualized_volatility": None,
        "sharpe": None,
        "sortino": None,
        "calmar": None,
        "turnover": None,
        "cost_adjusted_return": None,
        "regime_by_regime_performance": None,
        "contribution_analysis": None,
        "stress_period_performance": None,
        "parameter_sensitivity": None,
    }

