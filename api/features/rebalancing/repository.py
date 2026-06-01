from __future__ import annotations

import sqlite3
from typing import Any, Optional

from api.features.rebalancing.models import RebalanceRunData
from api.features.rebalancing.schemas import RebalanceResultItem, RiskBudgetItem, SuggestionItem
from api.features.targets.schemas import TargetItem
from api.features.targets.repository import get_local_target_deviations


class RebalancingRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_suggestions(self, mode: Any) -> list[SuggestionItem]:
        targets = get_local_target_deviations(self._conn)
        return get_rebalancing_suggestions(targets)

    def run_rebalancing(self, mode: Any) -> RebalanceRunData:
        from api.features.macro.repository import MacroRepository

        macro_repo = MacroRepository(self._conn)
        macro = macro_repo.get_indicators()
        kpi = macro_repo.get_kpi_summary(macro)
        targets = get_local_target_deviations(self._conn)
        run_id, rows = self._record_rebalance_results(mode, targets, kpi.totalAssets)
        return RebalanceRunData(run_id=run_id, rows=rows)

    def get_results(self, mode: Optional[Any], limit: int) -> list[RebalanceResultItem]:
        if mode:
            rows = self._conn.execute("""
                SELECT * FROM rebalance_results
                WHERE mode=?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
            """, (str(mode), limit)).fetchall()
        else:
            rows = self._conn.execute("""
                SELECT * FROM rebalance_results
                ORDER BY created_at DESC, id DESC
                LIMIT ?
            """, (limit,)).fetchall()
        return [_rebalance_result_from_row(r) for r in rows]

    def get_risk_budget(self) -> list[RiskBudgetItem]:
        try:
            allocation_rows = self._conn.execute("""
                SELECT strategy_bucket, target_ratio, min_ratio, max_ratio
                FROM engine_allocations
                WHERE COALESCE(is_active, 1) = 1
                ORDER BY strategy_bucket
            """).fetchall()
        except sqlite3.OperationalError:
            return []

        if not allocation_rows:
            return []

        known_buckets = {row["strategy_bucket"] for row in allocation_rows}
        bucket_values = {bucket: 0.0 for bucket in known_buckets}
        try:
            holding_rows = self._conn.execute("""
                SELECT strategy_bucket, asset_class,
                       SUM(COALESCE(market_value, value, 0)) AS total
                FROM holdings
                WHERE COALESCE(market_value, value, 0) > 0
                GROUP BY strategy_bucket, asset_class
            """).fetchall()
        except sqlite3.OperationalError:
            holding_rows = []

        total_value = 0.0
        for row in holding_rows:
            value = float(row["total"] or 0)
            if value <= 0:
                continue
            bucket = row["strategy_bucket"]
            if bucket not in known_buckets or bucket == "BROKER_SYNC":
                bucket = _strategy_bucket_for_asset(row["asset_class"])
            bucket_values[bucket] = bucket_values.get(bucket, 0.0) + value
            total_value += value

        result: list[RiskBudgetItem] = []
        for row in allocation_rows:
            bucket = row["strategy_bucket"]
            current_ratio = bucket_values.get(bucket, 0.0) / total_value if total_value > 0 else 0.0
            target_ratio = float(row["target_ratio"] or 0)
            min_ratio = row["min_ratio"]
            max_ratio = row["max_ratio"]
            item = _risk_budget_item(
                bucket=bucket,
                current_ratio=current_ratio,
                target_ratio=target_ratio,
                min_ratio=float(min_ratio) if min_ratio is not None else None,
                max_ratio=float(max_ratio) if max_ratio is not None else None,
            )
            result.append(item)
        return result

    def record_rebalance_results(
        self,
        mode: str,
        targets: list[TargetItem],
        total_assets: float,
    ) -> tuple[int, list[RebalanceResultItem]]:
        return self._record_rebalance_results(mode, targets, total_assets)

    def _record_rebalance_results(
        self,
        mode: str,
        targets: list[TargetItem],
        total_assets: float,
    ) -> tuple[int, list[RebalanceResultItem]]:
        run_id = int(self._conn.execute("SELECT strftime('%s','now')").fetchone()[0])
        risk_budget_by_bucket = {
            item.strategyBucket: item
            for item in self.get_risk_budget()
        }
        rows: list[RebalanceResultItem] = []
        for target in targets:
            action, reason = _rebalance_action_reason(target)
            budget = risk_budget_by_bucket.get(_strategy_bucket_for_asset(target.asset_class))
            if (target.target_type or "asset_allocation") == "asset_allocation" and budget and budget.level != "normal":
                reason = f"{reason}; 위험예산 {budget.strategyBucket} {budget.level}"
            amount = round((target.deviation / 100.0) * total_assets, 2)
            cur = self._conn.execute("""
                INSERT INTO rebalance_results
                (run_id, mode, account_id, account_type, asset_class, current_ratio,
                 target_ratio, deviation, action, amount, reason)
                VALUES (?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                str(mode),
                target.asset_class,
                target.currentRatio,
                target.targetRatio,
                target.deviation,
                action,
                amount,
                reason,
            ))
            rows.append(RebalanceResultItem(
                id=cur.lastrowid,
                runId=run_id,
                mode=str(mode),
                assetClass=target.asset_class,
                currentRatio=target.currentRatio,
                targetRatio=target.targetRatio,
                deviation=target.deviation,
                action=action,
                amount=amount,
                reason=reason,
            ))
        self._conn.commit()
        return run_id, rows


def get_rebalancing_suggestions(targets: list[TargetItem]) -> list[SuggestionItem]:
    suggestions = []
    for t in targets:
        if t.level == "normal":
            action = "관망"
            reason = f"목표 비중 유지 ({t.deviation:+.1f}%)"
        elif t.deviation > 0:
            action = "비중 축소"
            reason = f"목표 초과 {t.deviation:.1f}%"
        else:
            action = "비중 확대"
            reason = f"목표 미달 {abs(t.deviation):.1f}%"
        suggestions.append(SuggestionItem(
            asset=t.asset_class,
            action=action,
            reason=reason,
            deviation=t.deviation,
        ))
    return suggestions


def _strategy_bucket_for_asset(asset_class: str | None) -> str:
    normalized = (asset_class or "").strip().upper().replace(" ", "_")
    defensive = {"BOND", "채권", "PENSION", "PENSION_SAVINGS", "IRP", "DEFENSIVE_CORE"}
    liquidity = {"CASH", "현금", "LIQUIDITY"}
    if normalized in defensive or (asset_class or "").strip() in defensive:
        return "DEFENSIVE_CORE"
    if normalized in liquidity or (asset_class or "").strip() in liquidity:
        return "LIQUIDITY"
    return "AGGRESSIVE_ALPHA"


def _risk_budget_item(
    *,
    bucket: str,
    current_ratio: float,
    target_ratio: float,
    min_ratio: float | None,
    max_ratio: float | None,
) -> RiskBudgetItem:
    deviation = current_ratio - target_ratio
    below_min = min_ratio is not None and current_ratio < min_ratio
    above_max = max_ratio is not None and current_ratio > max_ratio
    if below_min or above_max:
        level = "danger"
    elif abs(deviation) >= 0.05:
        level = "warning"
    else:
        level = "normal"

    if level == "normal":
        action = "HOLD"
        reason = "위험예산 범위 내"
    elif current_ratio > target_ratio:
        action = "REDUCE"
        reason = "위험예산 상한 점검 필요" if above_max else "목표 위험예산 초과"
    else:
        action = "INCREASE"
        reason = "위험예산 하한 점검 필요" if below_min else "목표 위험예산 미달"

    return RiskBudgetItem(
        strategyBucket=bucket,
        currentRatio=round(current_ratio * 100, 2),
        targetRatio=round(target_ratio * 100, 2),
        minRatio=round(min_ratio * 100, 2) if min_ratio is not None else None,
        maxRatio=round(max_ratio * 100, 2) if max_ratio is not None else None,
        deviation=round(deviation * 100, 2),
        level=level,
        action=action,
        reason=reason,
    )


def _rebalance_action_reason(target: TargetItem) -> tuple[str, str]:
    if target.level == "normal":
        return "HOLD", f"허용 범위 내 ({target.deviation:+.1f}%)"
    if target.deviation > 0:
        return "REDUCE", f"목표 초과 {target.deviation:.1f}%"
    return "INCREASE", f"목표 미달 {abs(target.deviation):.1f}%"


def _rebalance_result_from_row(row: sqlite3.Row) -> RebalanceResultItem:
    return RebalanceResultItem(
        id=row["id"],
        runId=row["run_id"],
        mode=str(row["mode"]),
        accountId=row["account_id"],
        accountType=row["account_type"],
        assetClass=row["asset_class"],
        currentRatio=row["current_ratio"],
        targetRatio=row["target_ratio"],
        deviation=row["deviation"],
        action=row["action"],
        amount=row["amount"],
        reason=row["reason"],
        createdAt=row["created_at"],
    )
