from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

from .modes import ModePolicy, TradingMode
from api.features.accounts.schemas import AccountSummary, AllocationItem
from api.features.holdings.schemas import TopMover
from api.features.system.schemas import ModeInfo, ProviderSyncResult
from api.features.targets.schemas import TargetItem


_SYMBOL_NAMES = {
    "KOSPI":  "코스피",
    "KOSDAQ": "코스닥",
    "SPY":    "S&P500 ETF",
    "QQQ":    "나스닥100 ETF",
    "GOLD":   "금",
    "WTI":    "WTI유가",
    "SMH":    "반도체 ETF",
    "SOXX":   "반도체(iShares)",
    "DXY":    "달러인덱스",
    "US10Y":  "미국10년채",
}


@dataclass(frozen=True)
class ProviderCapabilities:
    mode: TradingMode
    provider: str
    can_write_user_data: bool
    can_execute_orders: bool
    external_api: bool
    order_policy: str


class BaseDataProvider:
    """Read facade shared by all trading modes."""

    def __init__(self, policy: ModePolicy):
        self.policy = policy

    @property
    def mode(self) -> TradingMode:
        return self.policy.mode

    @property
    def name(self) -> str:
        return self.policy.provider

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            mode=self.policy.mode,
            provider=self.policy.provider,
            can_write_user_data=self.policy.can_write_user_data,
            can_execute_orders=self.policy.can_execute_orders,
            external_api=self.policy.external_api,
            order_policy=self.policy.order_policy,
        )

    def mode_info(self) -> ModeInfo:
        return ModeInfo(
            mode=self.policy.mode,
            provider=self.policy.provider,
            dbWriteScope=self.policy.db_write_scope,
            externalApi=self.policy.external_api,
            orderPolicy=self.policy.order_policy,
            canWriteUserData=self.policy.can_write_user_data,
            canExecuteOrders=self.policy.can_execute_orders,
        )

    def assert_user_write_allowed(self) -> None:
        if not self.policy.can_write_user_data:
            raise PermissionError(f"{self.mode.value} mode is read-only")

    def get_accounts(self, conn: sqlite3.Connection) -> list[AccountSummary]:
        rows = conn.execute("SELECT * FROM accounts ORDER BY id").fetchall()
        result = []
        for a in rows:
            holdings = conn.execute(
                "SELECT SUM(market_value) as total, SUM(profit) as profit FROM holdings WHERE account_id=?",
                (a["id"],)
            ).fetchone()
            total_val = holdings["total"] or a["initial_value"] or 0
            profit = holdings["profit"] or 0
            profit_rate = round(profit / (total_val - profit) * 100, 2) if (total_val - profit) > 0 else 0.0
            result.append(AccountSummary(
                id=a["id"],
                name=a["name"],
                type=a["type"] or "",
                value=total_val,
                profit=profit,
                profitRate=profit_rate,
                accountType=a["account_type"] if "account_type" in a.keys() else a["type"],
                connectionStatus=a["connection_status"] if "connection_status" in a.keys() else "UNLINKED",
                tradeStatus=a["trade_status"] if "trade_status" in a.keys() else "ORDER_DISABLED",
                includeInRebalancing=bool(a["include_in_rebalancing"]) if "include_in_rebalancing" in a.keys() else True,
                dataSource=a["data_source"] if "data_source" in a.keys() else "MANUAL",
                lastSyncedAt=a["last_synced_at"] if "last_synced_at" in a.keys() else None,
            ))
        return result

    def get_target_deviations(self, conn: sqlite3.Connection) -> list[TargetItem]:
        targets = conn.execute(
            "SELECT id, target_type, asset_class, target_value, warning_thr, danger_thr FROM targets"
        ).fetchall()

        db_allocation = _allocation_from_holdings(conn)
        fallback_allocation = {
            "국내주식": 28.7, "해외주식": 34.2, "채권": 7.8,
            "ETF": 14.9, "현금": 10.1, "기타/대기": 4.3,
        }

        def _monthly_invest_actual() -> float:
            try:
                today = date.today()
                month_start = today.replace(day=1).isoformat()
                rows = conn.execute(
                    """SELECT total_value FROM account_snapshots
                       WHERE snapshot_at >= ? ORDER BY snapshot_at ASC LIMIT 1""",
                    (month_start,),
                ).fetchone()
                latest = conn.execute(
                    "SELECT SUM(total_value) AS s FROM account_snapshots WHERE account_id IN "
                    "(SELECT DISTINCT account_id FROM account_snapshots WHERE snapshot_at >= ?) "
                    "AND snapshot_at = (SELECT MAX(snapshot_at) FROM account_snapshots a2 "
                    "WHERE a2.account_id = account_snapshots.account_id)",
                    (month_start,),
                ).fetchone()
                if rows and latest and latest["s"]:
                    first_val = float(rows["total_value"])
                    last_val = float(latest["s"])
                    return max(0.0, last_val - first_val)
            except Exception:
                pass
            return 0.0

        def _ytd_return_rate() -> float:
            try:
                year_start = date.today().replace(month=1, day=1).isoformat()
                first = conn.execute(
                    "SELECT SUM(total_value) AS s FROM account_snapshots "
                    "WHERE snapshot_at >= ? ORDER BY snapshot_at ASC LIMIT 1",
                    (year_start,),
                ).fetchone()
                latest = conn.execute(
                    "SELECT SUM(total_value) AS s FROM account_snapshots "
                    "WHERE account_id IN (SELECT DISTINCT account_id FROM account_snapshots) "
                    "AND snapshot_at = (SELECT MAX(snapshot_at) FROM account_snapshots a2 "
                    "WHERE a2.account_id = account_snapshots.account_id)",
                ).fetchone()
                if first and latest and first["s"] and latest["s"] and float(first["s"]) > 0:
                    return round((float(latest["s"]) - float(first["s"])) / float(first["s"]) * 100, 2)
            except Exception:
                pass
            return 0.0

        result = []
        for t in targets:
            t_type = t["target_type"] or "asset_allocation"
            target_val = t["target_value"]

            if t_type == "asset_allocation":
                if db_allocation:
                    curr = db_allocation.get(t["asset_class"], 0.0)
                elif self.mode == TradingMode.MOCK:
                    curr = fallback_allocation.get(t["asset_class"], target_val)
                else:
                    curr = 0.0
                unit = "%"
            elif t_type == "monthly_invest":
                curr = _monthly_invest_actual()
                unit = "원"
            elif t_type == "return_rate":
                curr = _ytd_return_rate()
                unit = "%"
            else:
                curr = target_val
                unit = "%"

            if t_type == "monthly_invest" and target_val > 0:
                dev = round((curr - target_val) / target_val * 100, 2)
            else:
                dev = round(curr - target_val, 2)

            if abs(dev) >= t["danger_thr"]:
                level = "danger"
            elif abs(dev) >= t["warning_thr"]:
                level = "warning"
            else:
                level = "normal"

            result.append(TargetItem(
                id=t["id"],
                asset_class=t["asset_class"],
                target_type=t_type,
                currentRatio=curr,
                targetRatio=target_val,
                deviation=dev,
                level=level,
                unit=unit,
            ))
        return result

    def get_allocation(self, conn: sqlite3.Connection) -> list[AllocationItem]:
        rows = conn.execute("""
            SELECT asset_class, SUM(market_value) as total
            FROM holdings
            WHERE asset_class IS NOT NULL
            GROUP BY asset_class
            ORDER BY total DESC
        """).fetchall()
        if not rows:
            return []
        grand_total = sum(r["total"] for r in rows if r["total"])
        if grand_total <= 0:
            return []
        return [
            AllocationItem(
                asset=r["asset_class"],
                value=r["total"],
                ratio=round(r["total"] / grand_total * 100, 1),
            )
            for r in rows
        ]

    def get_top_movers(self, conn: sqlite3.Connection) -> list[TopMover]:
        symbols = ["KOSPI", "KOSDAQ", "SPY", "QQQ", "GOLD", "WTI", "SMH", "US10Y"]
        result = []
        for sym in symbols:
            rows = conn.execute(
                "SELECT value, date FROM indicators WHERE indicator=? ORDER BY date DESC LIMIT 2",
                (sym,)
            ).fetchall()
            if not rows:
                continue
            curr = rows[0]["value"]
            prev = rows[1]["value"] if len(rows) > 1 else None
            if curr is None:
                continue
            change_rate = round((curr - prev) / prev * 100, 2) if prev and prev > 0 else 0.0
            result.append(TopMover(
                symbol=sym,
                name=_SYMBOL_NAMES.get(sym, sym),
                price=round(curr, 2),
                changeRate=change_rate,
                contribution=None,
            ))
        return result

    def sync_accounts(self, conn: sqlite3.Connection) -> ProviderSyncResult:
        raise NotImplementedError(f"{self.name} does not support account sync yet")


def _allocation_from_holdings(conn: sqlite3.Connection) -> dict[str, float]:
    rows = conn.execute("""
        SELECT asset_class, SUM(market_value) AS total
        FROM holdings
        WHERE asset_class IS NOT NULL
          AND asset_class != ''
          AND COALESCE(market_value, 0) > 0
        GROUP BY asset_class
    """).fetchall()
    total = sum(float(r["total"] or 0) for r in rows)
    if total <= 0:
        return {}
    return {r["asset_class"]: round(float(r["total"] or 0) / total * 100, 2) for r in rows}
