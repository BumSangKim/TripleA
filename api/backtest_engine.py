from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

from .market_data_service import (
    AssetUniverseItem,
    get_asset_universe,
    get_fx_rate_on_or_before,
    get_price_on_or_before,
    validate_market_data_coverage,
)
from .features.market_data.trade_data_service import SqliteTradeSnapshotReader
from .strategy.triplea_allocator import TripleAAllocator
from .strategy.types import AllocationDecision, AllocationTarget


class BacktestAllocator(Protocol):
    def asset_codes(self) -> list[str]:
        ...

    def allocate(
        self,
        as_of_date: date,
        *,
        previous_weights: dict[str, float] | None = None,
    ) -> AllocationDecision:
        ...


@dataclass(frozen=True)
class BacktestConfig:
    start_date: date
    end_date: date
    initial_capital: float
    rebalance_frequency: str
    strategy_mode: str = "triplea_dynamic"
    risk_profile: str = "balanced"
    universe_id: str = "default_global"
    base_currency: str = "KRW"
    fee_bps: float = 0.0
    slippage_bps: float = 0.0
    tax_bps: float = 0.0
    data_lookback_years: int = 5


@dataclass(frozen=True)
class BacktestPointResult:
    point_date: date
    portfolio_value: float
    drawdown: float


@dataclass(frozen=True)
class BacktestPositionResult:
    point_date: date
    asset_code: str
    quantity: float
    price: float
    fx_rate: float
    market_value: float
    weight: float


@dataclass(frozen=True)
class BacktestTradeResult:
    trade_date: date
    asset_code: str
    side: str
    quantity: float
    price: float
    fx_rate: float
    gross_amount: float
    fee: float
    slippage: float
    tax: float
    net_amount: float
    reason: str


@dataclass(frozen=True)
class BacktestEngineResult:
    points: list[BacktestPointResult]
    positions: list[BacktestPositionResult]
    trades: list[BacktestTradeResult]
    decisions: list[AllocationDecision]
    total_return: float
    annual_return: float
    max_drawdown: float
    volatility: float


class BacktestEngine:
    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        allocator: BacktestAllocator | None = None,
    ):
        self.conn = conn
        self.allocator = allocator

    def run(self, config: BacktestConfig) -> BacktestEngineResult:
        _validate_config(config)
        allocator = self.allocator or TripleAAllocator.from_config(
            self.conn,
            risk_profile=config.risk_profile,
            universe_id=config.universe_id,
            strategy_mode=config.strategy_mode,
            trade_snapshot_reader=SqliteTradeSnapshotReader(self.conn),
        )
        asset_codes = allocator.asset_codes()
        coverage = validate_market_data_coverage(
            self.conn,
            asset_codes,
            config.start_date,
            config.end_date,
            base_currency=config.base_currency,
        )
        if not coverage.ok:
            raise ValueError("Market data coverage is insufficient: " + "; ".join(coverage.missing_messages))

        assets = {
            asset.asset_code: asset
            for asset in get_asset_universe(self.conn, active_only=False)
            if asset.asset_code in asset_codes
        }
        valuation_dates = _valuation_dates(self.conn, asset_codes, config.start_date, config.end_date)
        rebalance_dates = set(_rebalance_dates(config.start_date, config.end_date, config.rebalance_frequency))

        quantities = {asset_code: 0.0 for asset_code in asset_codes}
        points: list[BacktestPointResult] = []
        positions: list[BacktestPositionResult] = []
        trades: list[BacktestTradeResult] = []
        decisions: list[AllocationDecision] = []
        peak = config.initial_capital
        previous_value: float | None = None
        previous_weights: dict[str, float] | None = None
        period_returns: list[float] = []
        period_days: list[int] = []
        previous_date: date | None = None

        for current_date in valuation_dates:
            portfolio_value = _portfolio_value(
                self.conn,
                assets,
                quantities,
                current_date,
                config.base_currency,
            )
            if current_date == config.start_date and previous_value is None:
                portfolio_value = config.initial_capital

            if current_date in rebalance_dates:
                decision = allocator.allocate(current_date, previous_weights=previous_weights)
                targets = _targets_from_decision(decision, assets)
                decisions.append(decision)
                rebalance_trades = _rebalance(
                    self.conn,
                    assets,
                    quantities,
                    targets,
                    current_date,
                    portfolio_value,
                    config.base_currency,
                    config.fee_bps,
                    config.slippage_bps,
                    config.tax_bps,
                    initial=current_date == config.start_date,
                )
                trades.extend(rebalance_trades)
                previous_weights = decision.final_weights
                portfolio_value = _portfolio_value(
                    self.conn,
                    assets,
                    quantities,
                    current_date,
                    config.base_currency,
                )

            peak = max(peak, portfolio_value)
            drawdown = (portfolio_value / peak - 1) * 100 if peak > 0 else 0.0
            points.append(BacktestPointResult(
                point_date=current_date,
                portfolio_value=round(portfolio_value, 2),
                drawdown=round(drawdown, 2),
            ))
            positions.extend(_snapshot_positions(
                self.conn,
                assets,
                quantities,
                current_date,
                portfolio_value,
                config.base_currency,
            ))

            if previous_value is not None and previous_value > 0 and previous_date is not None:
                period_returns.append(portfolio_value / previous_value - 1)
                period_days.append(max((current_date - previous_date).days, 1))
            previous_value = portfolio_value
            previous_date = current_date

        final_value = points[-1].portfolio_value
        total_return = round((final_value / config.initial_capital - 1) * 100, 2)
        elapsed_years = max((config.end_date - config.start_date).days / 365.0, 1 / 365.0)
        annual_return = round(((final_value / config.initial_capital) ** (1 / elapsed_years) - 1) * 100, 2)
        max_drawdown = round(abs(min(point.drawdown for point in points)), 2)
        volatility = round(_annualized_volatility(period_returns, period_days), 2)
        return BacktestEngineResult(
            points=points,
            positions=positions,
            trades=trades,
            decisions=decisions,
            total_return=total_return,
            annual_return=annual_return,
            max_drawdown=max_drawdown,
            volatility=volatility,
        )


def _validate_config(config: BacktestConfig) -> None:
    if config.start_date >= config.end_date:
        raise ValueError("startDate must be before endDate")
    if config.initial_capital <= 0:
        raise ValueError("initialCapital must be greater than zero")


def _valuation_dates(
    conn: sqlite3.Connection,
    asset_codes: list[str],
    start: date,
    end: date,
) -> list[date]:
    placeholders = ",".join("?" for _ in asset_codes)
    rows = []
    if asset_codes:
        rows = conn.execute(
            f"""
            SELECT DISTINCT price_date
            FROM market_prices
            WHERE asset_code IN ({placeholders})
              AND price_date BETWEEN ? AND ?
            ORDER BY price_date
            """,
            [*asset_codes, start.isoformat(), end.isoformat()],
        ).fetchall()
    dates = {_parse_date(row["price_date"]) for row in rows}
    dates.update({start, end})
    return sorted(dates)


def _rebalance_dates(start: date, end: date, frequency: str) -> list[date]:
    normalized = (frequency or "monthly").strip().lower()
    if normalized == "weekly":
        dates = _stepped_dates(start, end, lambda current: current + timedelta(days=7))
    elif normalized == "monthly":
        dates = _stepped_dates(start, end, lambda current: _advance_months(current, 1))
    elif normalized == "quarterly":
        dates = _stepped_dates(start, end, lambda current: _advance_months(current, 3))
    else:
        raise ValueError("rebalanceFrequency must be one of weekly, monthly, quarterly")
    return dates


def _stepped_dates(start: date, end: date, advance) -> list[date]:
    dates = [start]
    current = start
    while True:
        next_date = advance(current)
        if next_date >= end:
            break
        dates.append(next_date)
        current = next_date
    return dates


def _advance_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, _last_day_of_month(year, month))
    return date(year, month, day)


def _last_day_of_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - timedelta(days=1)).day


def _targets_from_decision(
    decision: AllocationDecision,
    assets: dict[str, AssetUniverseItem],
) -> list[AllocationTarget]:
    targets: list[AllocationTarget] = []
    for asset_code, weight in decision.final_weights.items():
        if weight <= 0:
            continue
        asset = assets.get(asset_code)
        if not asset:
            raise KeyError(f"Asset metadata is missing for {asset_code}")
        targets.append(AllocationTarget(
            asset_class=asset.asset_class,
            asset_code=asset.asset_code,
            currency=asset.currency,
            target_weight=weight,
            bucket=None,
        ))
    if not targets:
        raise ValueError("allocator produced no positive targets")
    return targets


def _rebalance(
    conn: sqlite3.Connection,
    assets: dict[str, AssetUniverseItem],
    quantities: dict[str, float],
    targets: list[AllocationTarget],
    current_date: date,
    portfolio_value: float,
    base_currency: str,
    fee_bps: float,
    slippage_bps: float,
    tax_bps: float,
    *,
    initial: bool,
) -> list[BacktestTradeResult]:
    trades: list[BacktestTradeResult] = []
    reason = "INITIAL_ALLOCATE" if initial else "REBALANCE"
    target_by_asset = {target.asset_code: target for target in targets}
    cash_asset_code = _cash_asset_code(assets, target_by_asset)
    total_cost = 0.0

    for target in targets:
        if target.asset_code == cash_asset_code:
            continue
        asset = assets[target.asset_code]
        price, fx_rate = _pricing(conn, asset, current_date, base_currency)
        unit_value = price * fx_rate
        desired_value = portfolio_value * target.target_weight
        desired_quantity = desired_value / unit_value if unit_value > 0 else 0.0
        delta = desired_quantity - quantities.get(target.asset_code, 0.0)
        if abs(delta) <= 1e-10:
            continue
        side = "BUY" if delta > 0 else "SELL"
        trade_quantity = abs(delta)
        gross_amount = trade_quantity * price * fx_rate
        fee = gross_amount * max(fee_bps, 0.0) / 10000.0
        slippage = gross_amount * max(slippage_bps, 0.0) / 10000.0
        tax = gross_amount * max(tax_bps, 0.0) / 10000.0
        net_amount = gross_amount + fee + slippage + tax if side == "BUY" else gross_amount - fee - slippage - tax
        quantities[target.asset_code] = desired_quantity
        total_cost += fee + slippage + tax
        trades.append(BacktestTradeResult(
            trade_date=current_date,
            asset_code=target.asset_code,
            side=side,
            quantity=trade_quantity,
            price=price,
            fx_rate=fx_rate,
            gross_amount=round(gross_amount, 2),
            fee=round(fee, 2),
            slippage=round(slippage, 2),
            tax=round(tax, 2),
            net_amount=round(net_amount, 2),
            reason=reason,
        ))

    if cash_asset_code:
        cash_asset = assets[cash_asset_code]
        previous_cash_quantity = quantities.get(cash_asset_code, 0.0)
        non_cash_value = sum(
            _asset_value(conn, asset, quantities.get(asset_code, 0.0), current_date, base_currency)
            for asset_code, asset in assets.items()
            if asset_code != cash_asset_code
        )
        target_cash_quantity = max(portfolio_value - non_cash_value - total_cost, 0.0)
        delta = target_cash_quantity - previous_cash_quantity
        quantities[cash_asset_code] = target_cash_quantity
        if abs(delta) > 1e-10:
            price, fx_rate = _pricing(conn, cash_asset, current_date, base_currency)
            gross_amount = abs(delta) * price * fx_rate
            trades.append(BacktestTradeResult(
                trade_date=current_date,
                asset_code=cash_asset_code,
                side="BUY" if delta > 0 else "SELL",
                quantity=abs(delta),
                price=price,
                fx_rate=fx_rate,
                gross_amount=round(gross_amount, 2),
                fee=0.0,
                slippage=0.0,
                tax=0.0,
                net_amount=round(gross_amount, 2),
                reason=f"{reason}_CASH_BALANCE",
            ))
    return trades


def _portfolio_value(
    conn: sqlite3.Connection,
    assets: dict[str, AssetUniverseItem],
    quantities: dict[str, float],
    current_date: date,
    base_currency: str,
) -> float:
    total = 0.0
    for asset_code, quantity in quantities.items():
        asset = assets[asset_code]
        price, fx_rate = _pricing(conn, asset, current_date, base_currency)
        total += quantity * price * fx_rate
    return total


def _snapshot_positions(
    conn: sqlite3.Connection,
    assets: dict[str, AssetUniverseItem],
    quantities: dict[str, float],
    current_date: date,
    portfolio_value: float,
    base_currency: str,
) -> list[BacktestPositionResult]:
    results: list[BacktestPositionResult] = []
    for asset_code, quantity in quantities.items():
        asset = assets[asset_code]
        price, fx_rate = _pricing(conn, asset, current_date, base_currency)
        market_value = quantity * price * fx_rate
        weight = market_value / portfolio_value if portfolio_value > 0 else 0.0
        results.append(BacktestPositionResult(
            point_date=current_date,
            asset_code=asset_code,
            quantity=round(quantity, 10),
            price=round(price, 6),
            fx_rate=round(fx_rate, 6),
            market_value=round(market_value, 2),
            weight=round(weight, 6),
        ))
    return results


def _pricing(
    conn: sqlite3.Connection,
    asset: AssetUniverseItem,
    current_date: date,
    base_currency: str,
) -> tuple[float, float]:
    if asset.source_type == "manual":
        return 1.0, 1.0
    _, price = get_price_on_or_before(conn, asset.asset_code, current_date)
    _, fx_rate = get_fx_rate_on_or_before(
        conn,
        asset.currency,
        current_date,
        quote_currency=base_currency,
    )
    return price, fx_rate


def _asset_value(
    conn: sqlite3.Connection,
    asset: AssetUniverseItem,
    quantity: float,
    current_date: date,
    base_currency: str,
) -> float:
    price, fx_rate = _pricing(conn, asset, current_date, base_currency)
    return quantity * price * fx_rate


def _cash_asset_code(
    assets: dict[str, AssetUniverseItem],
    targets: dict[str, AllocationTarget],
) -> str | None:
    for asset_code in targets:
        asset = assets.get(asset_code)
        if asset and _is_cash_asset(asset):
            return asset_code
    return None


def _is_cash_asset(asset: AssetUniverseItem) -> bool:
    return asset.source_type == "manual" or asset.asset_code.startswith("CASH_")


def _annualized_volatility(period_returns: list[float], period_days: list[int]) -> float:
    if len(period_returns) < 2:
        return 0.0
    mean = sum(period_returns) / len(period_returns)
    variance = sum((value - mean) ** 2 for value in period_returns) / (len(period_returns) - 1)
    average_days = max(sum(period_days) / len(period_days), 1)
    return math.sqrt(variance) * math.sqrt(365 / average_days) * 100


def _parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])
