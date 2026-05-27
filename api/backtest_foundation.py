from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Protocol


class BacktestFoundationError(ValueError):
    pass


@dataclass(frozen=True)
class BacktestWarning:
    code: str
    message: str
    severity: str = "WARNING"
    source: str = "backtest"


@dataclass(frozen=True)
class SimulationConfig:
    start_date: date
    end_date: date
    frequency: str = "monthly"
    initial_capital: float = 0.0
    data_snapshot_id: str = "snapshot"
    parameter_version: str = "phase6_v1"
    model_version: str = "backtest_foundation_v1"
    warnings: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise BacktestFoundationError("start_date must be on or before end_date")
        if self.initial_capital < 0:
            raise BacktestFoundationError("initial_capital must be non-negative")
        _require_text(self.data_snapshot_id, "data_snapshot_id")
        _require_text(self.parameter_version, "parameter_version")
        _require_text(self.model_version, "model_version")


@dataclass(frozen=True, order=True)
class SimulationDate:
    as_of_date: date
    data_snapshot_id: str
    parameter_version: str
    model_version: str
    warnings: list[str] = field(default_factory=list, compare=False)
    reason_codes: list[str] = field(default_factory=list, compare=False)

    def __post_init__(self) -> None:
        if self.as_of_date is None:
            raise BacktestFoundationError("as_of_date is required")
        _require_text(self.data_snapshot_id, "data_snapshot_id")
        _require_text(self.parameter_version, "parameter_version")
        _require_text(self.model_version, "model_version")


@dataclass(frozen=True)
class HistoricalSnapshot:
    as_of_date: date
    data_snapshot_id: str
    data: dict[str, Any]
    parameter_version: str = "phase6_v1"
    model_version: str = "backtest_foundation_v1"
    warnings: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)

    def assert_available_for(self, simulation_date: date) -> None:
        if self.as_of_date > simulation_date:
            raise BacktestFoundationError("future historical snapshot rejected")


@dataclass(frozen=True)
class StrategyDecisionInput:
    as_of_date: date
    data_snapshot_id: str
    snapshot: HistoricalSnapshot
    portfolio_state: "PortfolioState"
    parameter_version: str
    model_version: str
    warnings: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StrategyDecisionOutput:
    as_of_date: date
    data_snapshot_id: str
    action: str = "HOLD"
    simulated_trades: list["SimulatedTrade"] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    parameter_version: str = "phase6_v1"
    model_version: str = "strategy_test_adapter_v1"

    def risk_increasing(self) -> bool:
        return any(trade.side == "BUY" for trade in self.simulated_trades)


@dataclass(frozen=True)
class BacktestResult:
    config: SimulationConfig
    equity_curve: list[tuple[date, float]]
    decisions: list[StrategyDecisionOutput]
    metrics: dict[str, float | None]
    warnings: list[str]
    reason_codes: list[str]
    parameter_version: str
    model_version: str


class HistoricalDataLoader(Protocol):
    def load(self, simulation_date: date) -> HistoricalSnapshot | None:
        ...


class StrategyPlugin(Protocol):
    def decide(self, decision_input: StrategyDecisionInput) -> StrategyDecisionOutput:
        ...


class SimulationClock:
    def __init__(self, config: SimulationConfig):
        self.config = config

    def dates(self) -> list[SimulationDate]:
        current = self.config.start_date
        output: list[SimulationDate] = []
        while current <= self.config.end_date:
            output.append(
                SimulationDate(
                    current,
                    self.config.data_snapshot_id,
                    self.config.parameter_version,
                    self.config.model_version,
                )
            )
            current = _advance(current, self.config.frequency)
        if output[-1].as_of_date != self.config.end_date:
            output.append(
                SimulationDate(
                    self.config.end_date,
                    self.config.data_snapshot_id,
                    self.config.parameter_version,
                    self.config.model_version,
                )
            )
        return output


class InMemoryHistoricalDataLoader:
    def __init__(self, snapshots: list[HistoricalSnapshot]):
        self.snapshots = sorted(snapshots, key=lambda snapshot: snapshot.as_of_date)

    def load(self, simulation_date: date) -> HistoricalSnapshot | None:
        candidates = [snapshot for snapshot in self.snapshots if snapshot.as_of_date <= simulation_date]
        if not candidates:
            return None
        snapshot = candidates[-1]
        snapshot.assert_available_for(simulation_date)
        return snapshot


@dataclass(frozen=True)
class PortfolioHolding:
    asset_id: str
    quantity: float
    price: float

    @property
    def market_value(self) -> float:
        return self.quantity * self.price


@dataclass(frozen=True)
class PortfolioState:
    cash: float
    holdings: dict[str, PortfolioHolding] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def total_value(self) -> float:
        return self.cash + sum(holding.market_value for holding in self.holdings.values())

    def weight(self, asset_id: str) -> float:
        total = self.total_value
        if total <= 0:
            return 0.0
        return self.holdings.get(asset_id, PortfolioHolding(asset_id, 0, 0)).market_value / total


@dataclass(frozen=True)
class SimulatedTrade:
    asset_id: str
    side: str
    quantity: float
    price: float
    reason: str = "simulation"

    def __post_init__(self) -> None:
        if self.side not in {"BUY", "SELL"}:
            raise BacktestFoundationError("simulated trade side must be BUY or SELL")
        if self.quantity <= 0:
            raise BacktestFoundationError("simulated trade quantity must be positive")
        if self.price <= 0:
            raise BacktestFoundationError("simulated trade price must be positive")

    @property
    def gross_value(self) -> float:
        return self.quantity * self.price


class TransactionCostModel(Protocol):
    def cost(self, trade: SimulatedTrade) -> float:
        ...


class TaxHook(Protocol):
    def tax(self, trade: SimulatedTrade, state: PortfolioState) -> float:
        ...


@dataclass(frozen=True)
class BpsTransactionCostModel:
    bps: float = 0.0

    def cost(self, trade: SimulatedTrade) -> float:
        return max(0.0, trade.gross_value * self.bps / 10_000.0)


@dataclass(frozen=True)
class NeutralTaxHook:
    bps: float = 0.0

    def tax(self, trade: SimulatedTrade, state: PortfolioState) -> float:
        return max(0.0, trade.gross_value * self.bps / 10_000.0)


def apply_simulated_trade(
    state: PortfolioState,
    trade: SimulatedTrade,
    cost_model: TransactionCostModel | None = None,
    tax_hook: TaxHook | None = None,
) -> PortfolioState:
    cost = (cost_model or BpsTransactionCostModel()).cost(trade)
    tax = (tax_hook or NeutralTaxHook()).tax(trade, state)
    holdings = dict(state.holdings)
    current = holdings.get(trade.asset_id, PortfolioHolding(trade.asset_id, 0.0, trade.price))
    if trade.side == "BUY":
        required_cash = trade.gross_value + cost + tax
        if state.cash < required_cash:
            return PortfolioState(state.cash, holdings, [*state.warnings, "INSUFFICIENT_CASH_BLOCKED_RISK_INCREASE"])
        holdings[trade.asset_id] = PortfolioHolding(trade.asset_id, current.quantity + trade.quantity, trade.price)
        return PortfolioState(state.cash - required_cash, holdings, state.warnings)
    sell_qty = min(current.quantity, trade.quantity)
    if sell_qty <= 0:
        return PortfolioState(state.cash, holdings, [*state.warnings, "MISSING_HOLDING_FOR_SELL"])
    holdings[trade.asset_id] = PortfolioHolding(trade.asset_id, current.quantity - sell_qty, trade.price)
    return PortfolioState(state.cash + sell_qty * trade.price - cost - tax, holdings, state.warnings)


class BacktestMetricCalculator:
    def calculate(
        self,
        equity_curve: list[tuple[date, float]],
        trades: list[SimulatedTrade] | None = None,
        *,
        annualization_days: int = 252,
    ) -> tuple[dict[str, float | None], list[str]]:
        warnings: list[str] = []
        if len(equity_curve) < 2:
            return _empty_metrics(), ["INSUFFICIENT_EQUITY_CURVE"]
        values = [value for _, value in equity_curve]
        returns = [values[i] / values[i - 1] - 1 for i in range(1, len(values)) if values[i - 1] > 0]
        total_return = values[-1] / values[0] - 1 if values[0] > 0 else None
        days = max((equity_curve[-1][0] - equity_curve[0][0]).days, 1)
        cagr = (values[-1] / values[0]) ** (365 / days) - 1 if values[0] > 0 else None
        max_drawdown = _max_drawdown(values)
        volatility = _stddev(returns) * math.sqrt(annualization_days) if len(returns) > 1 else 0.0
        downside = [item for item in returns if item < 0]
        downside_vol = _stddev(downside) * math.sqrt(annualization_days) if len(downside) > 1 else 0.0
        sharpe = None if volatility == 0 else (sum(returns) / len(returns)) * annualization_days / volatility
        sortino = None if downside_vol == 0 else (sum(returns) / len(returns)) * annualization_days / downside_vol
        calmar = None if max_drawdown == 0 else (cagr or 0.0) / abs(max_drawdown)
        turnover = sum(trade.gross_value for trade in trades or []) / max(sum(values) / len(values), 1.0)
        if sharpe is None:
            warnings.append("SHARPE_UNAVAILABLE_ZERO_VOLATILITY")
        return (
            {
                "total_return": total_return,
                "cagr": cagr,
                "mdd": max_drawdown,
                "annualized_volatility": volatility,
                "sharpe": sharpe,
                "sortino": sortino,
                "calmar": calmar,
                "turnover": turnover,
                "cost_adjusted_return": total_return,
                "tax_adjusted_return": total_return,
                "stress_period_performance": None,
                "regime_by_regime_performance": None,
                "parameter_sensitivity": None,
            },
            warnings,
        )


class BacktestRunner:
    def __init__(
        self,
        loader: HistoricalDataLoader,
        strategy: StrategyPlugin,
        cost_model: TransactionCostModel | None = None,
        tax_hook: TaxHook | None = None,
    ):
        self.loader = loader
        self.strategy = strategy
        self.cost_model = cost_model or BpsTransactionCostModel()
        self.tax_hook = tax_hook or NeutralTaxHook()

    def run(self, config: SimulationConfig) -> BacktestResult:
        state = PortfolioState(config.initial_capital)
        decisions: list[StrategyDecisionOutput] = []
        warnings: list[str] = []
        reason_codes: list[str] = []
        equity_curve: list[tuple[date, float]] = []
        trades: list[SimulatedTrade] = []
        for simulation_date in SimulationClock(config).dates():
            snapshot = self.loader.load(simulation_date.as_of_date)
            if snapshot is None:
                warnings.append("MISSING_HISTORICAL_SNAPSHOT_REVIEW_REQUIRED")
                equity_curve.append((simulation_date.as_of_date, state.total_value))
                continue
            snapshot.assert_available_for(simulation_date.as_of_date)
            decision = self.strategy.decide(
                StrategyDecisionInput(
                    as_of_date=simulation_date.as_of_date,
                    data_snapshot_id=snapshot.data_snapshot_id,
                    snapshot=snapshot,
                    portfolio_state=state,
                    parameter_version=config.parameter_version,
                    model_version=config.model_version,
                )
            )
            if decision.risk_increasing() and snapshot.warnings:
                warnings.append("RISK_INCREASE_BLOCKED_DUE_TO_SNAPSHOT_WARNING")
                decision = StrategyDecisionOutput(
                    simulation_date.as_of_date,
                    snapshot.data_snapshot_id,
                    "REVIEW_REQUIRED",
                    [],
                    ["RISK_INCREASE_BLOCKED_DUE_TO_SNAPSHOT_WARNING"],
                    ["REVIEW_REQUIRED"],
                    config.parameter_version,
                    config.model_version,
                )
            for trade in decision.simulated_trades:
                next_state = apply_simulated_trade(state, trade, self.cost_model, self.tax_hook)
                if "INSUFFICIENT_CASH_BLOCKED_RISK_INCREASE" in next_state.warnings:
                    warnings.extend(next_state.warnings)
                    break
                state = next_state
                trades.append(trade)
            decisions.append(decision)
            warnings.extend(decision.warnings)
            reason_codes.extend(decision.reason_codes)
            equity_curve.append((simulation_date.as_of_date, state.total_value))
        metrics, metric_warnings = BacktestMetricCalculator().calculate(equity_curve, trades)
        warnings.extend(metric_warnings)
        return BacktestResult(
            config=config,
            equity_curve=equity_curve,
            decisions=decisions,
            metrics=metrics,
            warnings=sorted(set(warnings)),
            reason_codes=sorted(set(reason_codes)),
            parameter_version=config.parameter_version,
            model_version=config.model_version,
        )


def _advance(current: date, frequency: str) -> date:
    normalized = (frequency or "monthly").lower()
    if normalized == "daily":
        return current + timedelta(days=1)
    if normalized == "weekly":
        return current + timedelta(days=7)
    if normalized == "quarterly":
        return _advance_months(current, 3)
    return _advance_months(current, 1)


def _advance_months(value: date, months: int) -> date:
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    day = min(value.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


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
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


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
        "tax_adjusted_return": None,
        "stress_period_performance": None,
        "regime_by_regime_performance": None,
        "parameter_sensitivity": None,
    }


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise BacktestFoundationError(f"{field_name} is required")
