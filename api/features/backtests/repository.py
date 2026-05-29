from __future__ import annotations

import json
import sqlite3
from datetime import date
from typing import Any

from api.features.backtests.schemas import (
    BacktestDecision,
    BacktestPoint,
    BacktestPosition,
    BacktestRunRequest,
    BacktestRunResponse,
    BacktestTrade,
)
from api.backtest_engine import BacktestConfig, BacktestEngine
from api.market_data_service import validate_market_data_coverage
from api.market_data_collector import collect_for_asset_codes
from api.strategy.triplea_allocator import TripleAAllocator
from api.strategy_config import list_risk_profiles, list_universe_ids

BACKTEST_STRATEGY_MODES = {"triplea_dynamic"}


class BacktestsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def run_backtest(self, request: BacktestRunRequest) -> BacktestRunResponse:
        start = _parse_backtest_date(request.startDate, "startDate")
        end = _parse_backtest_date(request.endDate, "endDate")
        if start >= end:
            raise ValueError("startDate must be before endDate")
        if request.initialCapital <= 0:
            raise ValueError("initialCapital must be greater than zero")

        frequency = (request.rebalanceFrequency or "monthly").strip().lower()
        strategy_mode = _normalize_backtest_option(
            request.strategyMode,
            "strategyMode",
            BACKTEST_STRATEGY_MODES,
        )
        risk_profile = _normalize_backtest_option(
            request.riskProfile,
            "riskProfile",
            set(list_risk_profiles()),
        )
        universe_id = _normalize_backtest_option(
            request.universeId,
            "universeId",
            set(list_universe_ids()),
        )
        base_currency = (request.baseCurrency or "KRW").strip().upper()
        if not base_currency:
            raise ValueError("baseCurrency must not be empty")
        fee_bps = _non_negative_bps(request.feeBps, "feeBps")
        slippage_bps = _non_negative_bps(request.slippageBps, "slippageBps")
        tax_bps = _non_negative_bps(request.taxBps, "taxBps")
        if request.dataLookbackYears < 1:
            raise ValueError("dataLookbackYears must be at least 1")
        if request.initialSeedPolicy not in {"CURRENT", "EQUAL_WEIGHT", "MINIMAL_PROBE", "VIRTUAL_OBSERVATION", "RANDOMIZED"}:
            raise ValueError("unsupported initialSeedPolicy")

        allocator = TripleAAllocator.from_config(
            self._conn,
            risk_profile=risk_profile,
            universe_id=universe_id,
            strategy_mode=strategy_mode,
        )

        asset_codes = allocator.asset_codes()
        coverage = validate_market_data_coverage(self._conn, asset_codes, start, end)
        if not coverage.ok:
            import logging
            logger = logging.getLogger("uvicorn.error")
            missing = "; ".join(coverage.missing_messages)
            logger.info("[run_backtest] coverage insufficient (%s) — collecting data", missing)
            collect_for_asset_codes(self._conn, asset_codes, start, end)
            coverage = validate_market_data_coverage(self._conn, asset_codes, start, end)
            if not coverage.ok:
                missing = "; ".join(coverage.missing_messages)
                logger.warning("[run_backtest] coverage still incomplete after collection: %s", missing)
                raise ValueError(f"시장 데이터 수집 후에도 데이터가 부족합니다: {missing}")

        result = BacktestEngine(self._conn, allocator=allocator).run(
            BacktestConfig(
                start_date=start,
                end_date=end,
                initial_capital=request.initialCapital,
                rebalance_frequency=frequency,
                strategy_mode=strategy_mode,
                risk_profile=risk_profile,
                universe_id=universe_id,
                base_currency=base_currency,
                fee_bps=fee_bps,
                slippage_bps=slippage_bps,
                tax_bps=tax_bps,
                data_lookback_years=request.dataLookbackYears,
            ),
        )

        cur = self._conn.execute("""
            INSERT INTO backtest_runs
            (name, start_date, end_date, initial_capital, strategy_mode, risk_profile,
             universe_id, rebalance_frequency, base_currency, fee_bps, slippage_bps,
             tax_bps, data_lookback_years, status, total_return, annual_return,
             max_drawdown, volatility)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETED', ?, ?, ?, ?)
        """, (
            (request.name or "TripleA Dynamic Backtest").strip() or "TripleA Dynamic Backtest",
            start.isoformat(),
            end.isoformat(),
            request.initialCapital,
            strategy_mode,
            risk_profile,
            universe_id,
            frequency,
            base_currency,
            fee_bps,
            slippage_bps,
            tax_bps,
            request.dataLookbackYears,
            result.total_return,
            result.annual_return,
            result.max_drawdown,
            result.volatility,
        ))
        run_id = int(cur.lastrowid)
        self._conn.executemany("""
            INSERT INTO backtest_points
            (run_id, point_date, portfolio_value, drawdown)
            VALUES (?, ?, ?, ?)
        """, [
            (run_id, point.point_date.isoformat(), point.portfolio_value, point.drawdown)
            for point in result.points
        ])
        self._conn.executemany("""
            INSERT INTO backtest_positions
            (run_id, point_date, asset_code, quantity, price, fx_rate, market_value, weight)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                run_id,
                position.point_date.isoformat(),
                position.asset_code,
                position.quantity,
                position.price,
                position.fx_rate,
                position.market_value,
                position.weight,
            )
            for position in result.positions
        ])
        self._conn.executemany("""
            INSERT INTO backtest_trades
            (run_id, trade_date, asset_code, side, quantity, price, fx_rate,
             gross_amount, fee, slippage, tax, net_amount, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                run_id,
                trade.trade_date.isoformat(),
                trade.asset_code,
                trade.side,
                trade.quantity,
                trade.price,
                trade.fx_rate,
                trade.gross_amount,
                trade.fee,
                trade.slippage,
                trade.tax,
                trade.net_amount,
                trade.reason,
            )
            for trade in result.trades
        ])
        for decision in result.decisions:
            decision_cur = self._conn.execute("""
                INSERT INTO backtest_decisions
                (run_id, decision_date, strategy_mode, risk_profile, universe_id,
                 macro_regime, macro_score, bucket_weights_json, final_weights_json,
                 bottleneck_scores_json, reasons_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                decision.as_of_date.isoformat(),
                decision.strategy_mode,
                decision.risk_profile,
                decision.universe_id,
                decision.macro_regime,
                decision.macro_score,
                json.dumps(decision.bucket_weights, ensure_ascii=False, sort_keys=True),
                json.dumps(decision.final_weights, ensure_ascii=False, sort_keys=True),
                json.dumps(decision.bottleneck_scores, ensure_ascii=False, sort_keys=True),
                json.dumps(decision.reasons, ensure_ascii=False),
            ))
            decision_id = int(decision_cur.lastrowid)
            if request.enableDecisionLogging:
                from api.strategy.decision_logger import log_strategy_decision

                log_strategy_decision(
                    self._conn,
                    enabled=True,
                    decision_id=f"backtest:{run_id}:{decision_id}",
                    as_of_date=decision.as_of_date,
                    decision_type="backtest_allocation",
                    snapshot_id=None,
                    payload={
                        "run_id": run_id,
                        "parameter_set_id": request.parameterSetId,
                        "optimization_run_id": request.optimizationRunId,
                        "initial_seed_policy": request.initialSeedPolicy,
                        "final_weights": decision.final_weights,
                    },
                    reason_codes=decision.reasons,
                )
            self._conn.executemany("""
                INSERT INTO backtest_sector_decisions
                (run_id, decision_id, decision_date, sector_code, total_score,
                 trade_score, demand_score, supply_score, relative_strength_score,
                 regime, reasons_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    run_id,
                    decision_id,
                    decision.as_of_date.isoformat(),
                    score.sector_code,
                    score.total_score,
                    score.trade_score,
                    score.demand_score,
                    score.supply_score,
                    score.relative_strength_score,
                    score.regime,
                    json.dumps(score.reasons, ensure_ascii=False),
                )
                for score in decision.sector_scores
            ])
        self._conn.commit()
        return self.get_run(run_id)

    def list_runs(self, limit: int) -> list[BacktestRunResponse]:
        bounded_limit = max(1, min(int(limit or 20), 100))
        rows = self._conn.execute("""
            SELECT id FROM backtest_runs
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        """, (bounded_limit,)).fetchall()
        return [self.get_run(int(row["id"])) for row in rows]

    def get_run(self, run_id: int) -> BacktestRunResponse:
        row = self._conn.execute("SELECT * FROM backtest_runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise KeyError(f"backtest run {run_id} not found")
        point_rows = self._conn.execute("""
            SELECT point_date, portfolio_value, drawdown
            FROM backtest_points
            WHERE run_id=?
            ORDER BY point_date ASC, id ASC
        """, (run_id,)).fetchall()
        position_rows = self._conn.execute("""
            SELECT point_date, asset_code, quantity, price, fx_rate, market_value, weight
            FROM backtest_positions
            WHERE run_id=?
            ORDER BY point_date ASC, id ASC
        """, (run_id,)).fetchall()
        trade_rows = self._conn.execute("""
            SELECT trade_date, asset_code, side, quantity, price, fx_rate,
                   gross_amount, fee, slippage, tax, net_amount, reason
            FROM backtest_trades
            WHERE run_id=?
            ORDER BY trade_date ASC, id ASC
        """, (run_id,)).fetchall()
        decision_rows = self._conn.execute("""
            SELECT decision_date, strategy_mode, risk_profile, universe_id,
                   macro_regime, macro_score, bucket_weights_json,
                   final_weights_json, bottleneck_scores_json, reasons_json
            FROM backtest_decisions
            WHERE run_id=?
            ORDER BY decision_date ASC, id ASC
        """, (run_id,)).fetchall()
        return BacktestRunResponse(
            ok=True,
            runId=row["id"],
            name=row["name"] or "Backtest",
            startDate=row["start_date"],
            endDate=row["end_date"],
            initialCapital=row["initial_capital"],
            strategyMode=row["strategy_mode"] or "triplea_dynamic",
            riskProfile=row["risk_profile"] or "balanced",
            universeId=row["universe_id"] or "default_global",
            rebalanceFrequency=row["rebalance_frequency"] or "monthly",
            baseCurrency=row["base_currency"] or "KRW",
            feeBps=row["fee_bps"] or 0,
            slippageBps=row["slippage_bps"] or 0,
            taxBps=row["tax_bps"] or 0,
            dataLookbackYears=row["data_lookback_years"] or 5,
            status=row["status"] or "COMPLETED",
            totalReturn=row["total_return"] or 0,
            annualReturn=row["annual_return"] or 0,
            maxDrawdown=row["max_drawdown"] or 0,
            volatility=row["volatility"] or 0,
            points=[
                BacktestPoint(
                    date=point["point_date"],
                    value=point["portfolio_value"],
                    drawdown=point["drawdown"],
                )
                for point in point_rows
            ],
            positions=[
                BacktestPosition(
                    date=position["point_date"],
                    assetCode=position["asset_code"],
                    quantity=position["quantity"],
                    price=position["price"],
                    fxRate=position["fx_rate"],
                    marketValue=position["market_value"],
                    weight=position["weight"],
                )
                for position in position_rows
            ],
            trades=[
                BacktestTrade(
                    date=trade["trade_date"],
                    assetCode=trade["asset_code"],
                    side=trade["side"],
                    quantity=trade["quantity"],
                    price=trade["price"],
                    fxRate=trade["fx_rate"],
                    grossAmount=trade["gross_amount"],
                    fee=trade["fee"],
                    slippage=trade["slippage"],
                    tax=trade["tax"],
                    netAmount=trade["net_amount"],
                    reason=trade["reason"],
                )
                for trade in trade_rows
            ],
            decisions=[
                _backtest_decision_from_row(decision)
                for decision in decision_rows
            ],
            createdAt=row["created_at"],
        )

    def get_decisions(self, run_id: int) -> list[BacktestDecision]:
        _ensure_backtest_run(self._conn, run_id)
        rows = self._conn.execute("""
            SELECT decision_date, strategy_mode, risk_profile, universe_id,
                   macro_regime, macro_score, bucket_weights_json,
                   final_weights_json, bottleneck_scores_json, reasons_json
            FROM backtest_decisions
            WHERE run_id=?
            ORDER BY decision_date ASC, id ASC
        """, (run_id,)).fetchall()
        return [_backtest_decision_from_row(row) for row in rows]

    def get_positions(self, run_id: int) -> list[BacktestPosition]:
        _ensure_backtest_run(self._conn, run_id)
        rows = self._conn.execute("""
            SELECT point_date, asset_code, quantity, price, fx_rate, market_value, weight
            FROM backtest_positions
            WHERE run_id=?
            ORDER BY point_date ASC, id ASC
        """, (run_id,)).fetchall()
        return [
            BacktestPosition(
                date=row["point_date"],
                assetCode=row["asset_code"],
                quantity=row["quantity"],
                price=row["price"],
                fxRate=row["fx_rate"],
                marketValue=row["market_value"],
                weight=row["weight"],
            )
            for row in rows
        ]

    def get_trades(self, run_id: int) -> list[BacktestTrade]:
        _ensure_backtest_run(self._conn, run_id)
        rows = self._conn.execute("""
            SELECT trade_date, asset_code, side, quantity, price, fx_rate,
                   gross_amount, fee, slippage, tax, net_amount, reason
            FROM backtest_trades
            WHERE run_id=?
            ORDER BY trade_date ASC, id ASC
        """, (run_id,)).fetchall()
        return [
            BacktestTrade(
                date=row["trade_date"],
                assetCode=row["asset_code"],
                side=row["side"],
                quantity=row["quantity"],
                price=row["price"],
                fxRate=row["fx_rate"],
                grossAmount=row["gross_amount"],
                fee=row["fee"],
                slippage=row["slippage"],
                tax=row["tax"],
                netAmount=row["net_amount"],
                reason=row["reason"],
            )
            for row in rows
        ]


def _ensure_backtest_run(conn: sqlite3.Connection, run_id: int) -> None:
    row = conn.execute("SELECT 1 FROM backtest_runs WHERE id=?", (run_id,)).fetchone()
    if not row:
        raise KeyError(f"backtest run {run_id} not found")


def _backtest_decision_from_row(row: Any) -> BacktestDecision:
    return BacktestDecision(
        date=row["decision_date"],
        strategyMode=row["strategy_mode"],
        riskProfile=row["risk_profile"],
        universeId=row["universe_id"],
        macroRegime=row["macro_regime"],
        macroScore=row["macro_score"],
        bucketWeights=_decode_json_object(row["bucket_weights_json"]),
        finalWeights=_decode_json_object(row["final_weights_json"]),
        bottleneckScores=_decode_json_object(row["bottleneck_scores_json"]),
        reasons=_decode_json_list(row["reasons_json"]),
    )


def _decode_json_object(value: str | None) -> dict[str, float]:
    if not value:
        return {}
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        return {}
    return {str(key): float(item) for key, item in parsed.items()}


def _decode_json_list(value: str | None) -> list[str]:
    if not value:
        return []
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _parse_backtest_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be YYYY-MM-DD") from exc


def _normalize_backtest_option(value: str, field_name: str, allowed: set[str]) -> str:
    normalized = (value or "").strip().lower()
    if normalized not in allowed:
        options = ", ".join(sorted(allowed))
        raise ValueError(f"{field_name} must be one of {options}")
    return normalized


def _non_negative_bps(value: float, field_name: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise ValueError(f"{field_name} must be zero or greater")
    return parsed
