"""
api/services.py
비즈니스 로직 - 리밸런싱 계산, 데이터 조합
"""
from __future__ import annotations
import json
import sqlite3
from datetime import date
from typing import List, Optional
from .models import (
    MacroIndicator, TargetItem, SuggestionItem, AlertItem,
    KPISummary, AllocationItem, AccountSummary, TopMover, CalendarEvent, Insights,
    AccountPolicyItem, AccountSnapshotCreate, AccountSnapshotItem,
    RebalanceResultItem, RiskBudgetItem, OrderDraftResponse, OrderItem,
    BacktestRunRequest, BacktestRunResponse, BacktestPoint, BacktestPosition, BacktestTrade,
    BacktestDecision,
)
from .modes import TradingMode
from .backtest_engine import BacktestConfig, BacktestEngine
from .market_data_service import validate_market_data_coverage
from .market_data_collector import collect_for_asset_codes
from .strategy.triplea_allocator import TripleAAllocator
from .strategy_config import list_risk_profiles, list_universe_ids

BACKTEST_STRATEGY_MODES = {"triplea_dynamic"}

MACRO_KEY_MAP = {
    "cpi":          {"name": "CPI YoY",      "unit": "%"},
    "interest":     {"name": "기준금리",       "unit": "%"},
    "unemployment": {"name": "실업률",         "unit": "%"},
    "exchange_usd": {"name": "USD/KRW",       "unit": "원"},
    "vix":          {"name": "VIX",           "unit": "pt"},
    "pmi":          {"name": "PMI",           "unit": "pt"},
    "CPIAUCSL":     {"name": "CPI YoY",      "unit": "%"},
    "UNRATE":       {"name": "실업률",         "unit": "%"},
    "FEDFUNDS":     {"name": "기준금리",       "unit": "%"},
    "DGS10":        {"name": "미국 10년채",    "unit": "%"},
    "T10Y2Y":       {"name": "장단기 스프레드","unit": "%"},
    "VIXCLS":       {"name": "VIX",           "unit": "pt"},
    "ISM_PMI":      {"name": "ISM PMI",       "unit": "pt"},
    "USD_KRW":      {"name": "USD/KRW",       "unit": "원"},
    "WTI":          {"name": "WTI 유가",      "unit": "$"},
    "DXY":          {"name": "달러인덱스",     "unit": "pt"},
}

PREFERRED_MACRO_KEYS = [
    "CPIAUCSL", "cpi", "FEDFUNDS", "interest",
    "UNRATE", "unemployment", "USD_KRW", "exchange_usd",
    "VIXCLS", "vix", "ISM_PMI", "pmi", "DGS10", "T10Y2Y", "WTI", "DXY"
]


def get_macro_indicators(conn: sqlite3.Connection) -> List[MacroIndicator]:
    """DB에서 최신 경제지표 로드 (최대 12개)"""
    rows = conn.execute("""
        SELECT i.indicator, i.value, i.unit, i.date, i.source,
               prev.value AS prev_value
        FROM indicators i
        INNER JOIN (
            SELECT indicator, MAX(date) AS max_date
            FROM indicators GROUP BY indicator
        ) latest ON i.indicator = latest.indicator AND i.date = latest.max_date
        LEFT JOIN (
            SELECT indicator, value, date FROM indicators
        ) prev ON prev.indicator = i.indicator AND prev.date < i.date
        ORDER BY i.indicator
    """).fetchall()

    rows_dict = {r["indicator"]: r for r in rows}
    result = []

    for key in PREFERRED_MACRO_KEYS:
        if key in rows_dict:
            r = rows_dict[key]
            meta = MACRO_KEY_MAP.get(key, {"name": key, "unit": r["unit"] or ""})
            val = r["value"]
            prev = r["prev_value"]
            change = round(val - prev, 4) if val is not None and prev is not None else None
            if change is None:
                status = "stable"
            elif change > 0:
                status = "rising"
            else:
                status = "falling"
            result.append(MacroIndicator(
                key=key,
                name=meta["name"],
                value=val,
                unit=r["unit"] or meta["unit"],
                change=change,
                status=status,
                date=r["date"],
            ))

    # 지정 키 외 나머지도 추가 (최대 12개)
    for key, r in rows_dict.items():
        if len(result) >= 12:
            break
        if key in PREFERRED_MACRO_KEYS:
            continue
        meta = MACRO_KEY_MAP.get(key, {"name": key, "unit": r["unit"] or ""})
        val = r["value"]
        result.append(MacroIndicator(
            key=key,
            name=meta["name"],
            value=val,
            unit=r["unit"] or meta["unit"],
            change=None,
            status="stable",
            date=r["date"],
        ))
    return result


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


def get_target_deviations(conn: sqlite3.Connection, mode: TradingMode = TradingMode.TEST) -> List[TargetItem]:
    """목표 비중 vs 현재 비중 계산 (모든 target_type 지원)"""
    targets = conn.execute(
        "SELECT id, target_type, asset_class, target_value, warning_thr, danger_thr FROM targets"
    ).fetchall()

    db_allocation = _allocation_from_holdings(conn)
    fallback_allocation = {
        "국내주식": 28.7, "해외주식": 34.2, "채권": 7.8,
        "ETF": 14.9, "현금": 10.1, "기타/대기": 4.3,
    }

    # ── monthly_invest: 당월 account_snapshots 합계 ──────────────
    def _monthly_invest_actual() -> float:
        """당월 첫 스냅샷 대비 최신 스냅샷 총자산 증가분을 투자금액으로 근사"""
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

    # ── return_rate: YTD 수익률 계산 ─────────────────────────────
    def _ytd_return_rate() -> float:
        """연초 대비 현재 총자산 수익률(%) 계산"""
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
            elif mode == TradingMode.MOCK:
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

        # deviation: 비율 편차 (%)
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


def get_rebalancing_suggestions(targets: List[TargetItem]) -> List[SuggestionItem]:
    """룰 기반 리밸런싱 제안 생성"""
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


def generate_target_alerts(conn: sqlite3.Connection) -> int:
    """목표 비중 이탈 시 alerts 테이블에 자동 기록 (중복 방지: 오늘 이미 생성된 것은 건너뜀)"""
    targets = get_target_deviations(conn)
    created = 0
    for t in targets:
        if t.level == "normal":
            continue
        level_str = "danger" if t.level == "danger" else "warning"
        direction = "초과" if t.deviation > 0 else "부족"
        title = f"{t.asset_class} 비중 {direction} {abs(t.deviation):.1f}%"
        # 오늘 동일 제목 중복 확인
        existing = conn.execute("""
            SELECT id FROM dashboard_alerts
            WHERE title=? AND date(created_at)=date('now','localtime') LIMIT 1
        """, (title,)).fetchone()
        if existing:
            continue
        conn.execute("""
            INSERT INTO dashboard_alerts (level, category, title, message)
            VALUES (?, 'target', ?, ?)
        """, (
            level_str,
            title,
            f"현재 {t.currentRatio:.1f}% / 목표 {t.targetRatio:.1f}% (편차 {t.deviation:+.1f}%)",
        ))
        created += 1
    if created:
        conn.commit()
    return created


def get_recent_alerts(conn: sqlite3.Connection, limit: int = 10) -> List[AlertItem]:
    rows = conn.execute(
        "SELECT * FROM dashboard_alerts ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [
        AlertItem(
            id=r["id"], level=r["level"], category=r["category"],
            title=r["title"], message=r["message"],
            is_read=bool(r["is_read"]), created_at=r["created_at"],
        )
        for r in rows
    ]


def compute_macro_score(indicators: List[MacroIndicator]) -> int:
    """매크로 종합 점수 계산 (0~100)
    - 기준: stable 비율을 기반으로, VIX 수준에 따라 추가 조정
    """
    if not indicators:
        return 50
    stable = sum(1 for i in indicators if i.status == "stable")
    base_score = round(stable / len(indicators) * 100)
    # VIX 수준 조정
    vix = next(
        (i.value for i in indicators
         if i.value is not None and "VIX" in (i.key or "").upper()),
        None
    )
    if vix is not None:
        if vix > 30:
            base_score = max(0, base_score - 20)
        elif vix > 20:
            base_score = max(0, base_score - 10)
    return max(0, min(100, base_score))


def get_kpi_summary(conn: sqlite3.Connection, macro: Optional[List[MacroIndicator]] = None) -> KPISummary:
    """KPI 요약 - holdings 테이블에 저장된 실제 계좌 데이터만 사용."""
    macro_score = compute_macro_score(macro) if macro else None
    row = conn.execute("""
        SELECT
            COALESCE(SUM(market_value), 0) AS total_assets,
            COALESCE(SUM(profit), 0) AS total_profit
        FROM holdings
    """).fetchone()
    total_assets = float(row["total_assets"] or 0)
    total_profit = float(row["total_profit"] or 0)
    invested_principal = total_assets - total_profit
    profit_rate = round(total_profit / invested_principal * 100, 2) if invested_principal > 0 else 0.0

    return KPISummary(
        totalAssets=total_assets,
        cash=0,
        todayProfit=total_profit,
        todayProfitRate=profit_rate,
        riskLevel="보통",
        macroScore=macro_score,
    )


def get_accounts_from_db(conn: sqlite3.Connection) -> List[AccountSummary]:
    """실제 accounts + holdings 테이블에서 계좌 요약"""
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


def get_account_policies(conn: sqlite3.Connection) -> list[AccountPolicyItem]:
    rows = conn.execute("""
        SELECT id, account_type, role, deposit_policy, allowed_products,
               rebalance_priority, risk_note
        FROM account_policies
        ORDER BY account_type
    """).fetchall()
    return [
        AccountPolicyItem(
            id=r["id"],
            accountType=r["account_type"],
            role=r["role"],
            depositPolicy=r["deposit_policy"],
            allowedProducts=r["allowed_products"],
            rebalancePriority=r["rebalance_priority"],
            riskNote=r["risk_note"],
        )
        for r in rows
    ]


def save_manual_snapshot(
    conn: sqlite3.Connection,
    account_id: int,
    snapshot: AccountSnapshotCreate,
) -> AccountSnapshotItem:
    account = conn.execute("SELECT id FROM accounts WHERE id=?", (account_id,)).fetchone()
    if not account:
        raise KeyError(f"account {account_id} not found")

    snapshot_at = snapshot.snapshotAt or conn.execute(
        "SELECT datetime('now','localtime')"
    ).fetchone()[0]
    cur = conn.execute("""
        INSERT INTO account_snapshots
        (account_id, total_value, cash_value, domestic_stock_value, foreign_stock_value,
         bond_value, etf_value, pension_value, alt_value, snapshot_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        account_id,
        snapshot.totalValue,
        snapshot.cashValue,
        snapshot.domesticStockValue,
        snapshot.foreignStockValue,
        snapshot.bondValue,
        snapshot.etfValue,
        snapshot.pensionValue,
        snapshot.altValue,
        snapshot_at,
    ))
    conn.execute("""
        UPDATE accounts
        SET initial_value=?,
            data_source='MANUAL',
            connection_status='UNLINKED',
            last_synced_at=?
        WHERE id=?
    """, (snapshot.totalValue, snapshot_at, account_id))
    conn.commit()

    row = conn.execute(
        "SELECT * FROM account_snapshots WHERE id=?", (cur.lastrowid,)
    ).fetchone()
    return _snapshot_from_row(row)


def get_account_snapshots(
    conn: sqlite3.Connection,
    account_id: int,
    limit: int = 20,
) -> list[AccountSnapshotItem]:
    rows = conn.execute("""
        SELECT * FROM account_snapshots
        WHERE account_id=?
        ORDER BY snapshot_at DESC, id DESC
        LIMIT ?
    """, (account_id, limit)).fetchall()
    return [_snapshot_from_row(r) for r in rows]


def _snapshot_from_row(row: sqlite3.Row) -> AccountSnapshotItem:
    return AccountSnapshotItem(
        id=row["id"],
        accountId=row["account_id"],
        totalValue=row["total_value"],
        cashValue=row["cash_value"],
        domesticStockValue=row["domestic_stock_value"],
        foreignStockValue=row["foreign_stock_value"],
        bondValue=row["bond_value"],
        etfValue=row["etf_value"],
        pensionValue=row["pension_value"],
        altValue=row["alt_value"],
        snapshotAt=row["snapshot_at"],
        createdAt=row["created_at"],
    )


def set_account_rebalancing_inclusion(
    conn: sqlite3.Connection,
    account_id: int,
    include: bool,
) -> bool:
    cur = conn.execute(
        "UPDATE accounts SET include_in_rebalancing=? WHERE id=?",
        (1 if include else 0, account_id),
    )
    conn.commit()
    return cur.rowcount > 0


def get_risk_budget_items(conn: sqlite3.Connection) -> list[RiskBudgetItem]:
    try:
        allocation_rows = conn.execute("""
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
        holding_rows = conn.execute("""
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
    conn: sqlite3.Connection,
    mode: TradingMode,
    targets: list[TargetItem],
    total_assets: float,
) -> tuple[int, list[RebalanceResultItem]]:
    run_id = int(conn.execute("SELECT strftime('%s','now')").fetchone()[0])
    risk_budget_by_bucket = {
        item.strategyBucket: item
        for item in get_risk_budget_items(conn)
    }
    rows: list[RebalanceResultItem] = []
    for target in targets:
        action, reason = _rebalance_action_reason(target)
        budget = risk_budget_by_bucket.get(_strategy_bucket_for_asset(target.asset_class))
        if (target.target_type or "asset_allocation") == "asset_allocation" and budget and budget.level != "normal":
            reason = f"{reason}; 위험예산 {budget.strategyBucket} {budget.level}"
        amount = round((target.deviation / 100.0) * total_assets, 2)
        cur = conn.execute("""
            INSERT INTO rebalance_results
            (run_id, mode, account_id, account_type, asset_class, current_ratio,
             target_ratio, deviation, action, amount, reason)
            VALUES (?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            mode.value,
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
            mode=mode,
            assetClass=target.asset_class,
            currentRatio=target.currentRatio,
            targetRatio=target.targetRatio,
            deviation=target.deviation,
            action=action,
            amount=amount,
            reason=reason,
        ))
    conn.commit()
    return run_id, rows


def get_rebalance_results(
    conn: sqlite3.Connection,
    mode: TradingMode | None = None,
    limit: int = 50,
) -> list[RebalanceResultItem]:
    if mode:
        rows = conn.execute("""
            SELECT * FROM rebalance_results
            WHERE mode=?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        """, (mode.value, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM rebalance_results
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return [_rebalance_result_from_row(r) for r in rows]


def create_order_draft(
    conn: sqlite3.Connection,
    mode: TradingMode,
    source: str = "rebalancing",
    max_order_amount: float | None = None,
) -> OrderDraftResponse:
    if source != "rebalancing":
        raise ValueError("Only rebalancing order drafts are supported")
    if mode not in {TradingMode.PAPER, TradingMode.LIVE}:
        raise PermissionError(f"{mode.value} mode cannot create order drafts")

    total_assets = _portfolio_total_from_holdings(conn)
    targets = [
        target for target in get_target_deviations(conn, mode)
        if (target.target_type or "asset_allocation") == "asset_allocation" and target.level != "normal"
    ]
    status = "DRAFT"
    cur = conn.execute(
        """
        INSERT INTO order_drafts (mode, source, status, max_order_amount, total_amount)
        VALUES (?, ?, ?, ?, 0)
        """,
        (mode.value, source, status, max_order_amount),
    )
    draft_id = int(cur.lastrowid)

    items: list[OrderItem] = []
    for target in targets:
        side = "SELL" if target.deviation > 0 else "BUY"
        amount = round(abs(target.deviation) / 100.0 * total_assets, 2)
        if max_order_amount is not None:
            amount = min(amount, max_order_amount)
        if amount <= 0:
            continue
        reason = f"{target.asset_class} {target.deviation:+.1f}% 괴리 조정 후보"
        item_cur = conn.execute(
            """
            INSERT INTO order_items
            (draft_id, account_id, asset_class, side, amount, status, reason)
            VALUES (?, NULL, ?, ?, ?, 'DRAFT', ?)
            """,
            (draft_id, target.asset_class, side, amount, reason),
        )
        items.append(OrderItem(
            id=item_cur.lastrowid,
            draftId=draft_id,
            assetClass=target.asset_class,
            side=side,
            amount=amount,
            status="DRAFT",
            reason=reason,
        ))

    total_amount = round(sum(item.amount for item in items), 2)
    if not items:
        status = "EMPTY"
    conn.execute(
        "UPDATE order_drafts SET status=?, total_amount=? WHERE id=?",
        (status, total_amount, draft_id),
    )
    _insert_order_log(
        conn,
        draft_id=draft_id,
        mode=mode,
        event="DRAFT_CREATED",
        status=status,
        message=f"{len(items)} order candidates generated",
    )
    conn.commit()
    return _order_draft_response(conn, draft_id, message="주문 후보가 생성되었습니다.")


def approve_order_draft(
    conn: sqlite3.Connection,
    mode: TradingMode,
    draft_id: int,
    confirm_text: str | None = None,
) -> OrderDraftResponse:
    draft = conn.execute("SELECT * FROM order_drafts WHERE id=?", (draft_id,)).fetchone()
    if not draft:
        raise KeyError(f"order draft {draft_id} not found")
    if draft["mode"] != mode.value:
        raise PermissionError("Order draft mode does not match request mode")
    if mode == TradingMode.LIVE:
        raise PermissionError("Live order execution is disabled; this mode remains read-only")
    if mode != TradingMode.PAPER:
        raise PermissionError(f"{mode.value} mode cannot approve order drafts")
    if (confirm_text or "").strip() != "모의 주문을 승인합니다":
        raise ValueError("Paper order approval requires confirmText='모의 주문을 승인합니다'")
    if draft["status"] == "EMPTY":
        raise ValueError("Empty order draft cannot be approved")

    status = "APPROVED_NOT_SENT"
    conn.execute(
        """
        UPDATE order_drafts
        SET status=?, approved_at=datetime('now','localtime')
        WHERE id=?
        """,
        (status, draft_id),
    )
    conn.execute(
        "UPDATE order_items SET status=? WHERE draft_id=?",
        (status, draft_id),
    )
    _insert_order_log(
        conn,
        draft_id=draft_id,
        mode=mode,
        event="PAPER_APPROVED",
        status=status,
        message="Paper order draft manually approved; broker submission is not implemented yet",
    )
    conn.commit()
    return _order_draft_response(conn, draft_id, message="모의 주문 후보가 승인 로그로 기록되었습니다.")


def list_order_drafts(
    conn: sqlite3.Connection,
    mode: TradingMode | None = None,
    limit: int = 20,
) -> list[OrderDraftResponse]:
    if mode:
        rows = conn.execute(
            """
            SELECT id FROM order_drafts
            WHERE mode=?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (mode.value, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id FROM order_drafts
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_order_draft_response(conn, int(row["id"])) for row in rows]


# ── Backtests ────────────────────────────────────────────────────────
def run_backtest(
    conn: sqlite3.Connection,
    request: BacktestRunRequest,
) -> BacktestRunResponse:
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

    allocator = TripleAAllocator.from_config(
        conn,
        risk_profile=risk_profile,
        universe_id=universe_id,
        strategy_mode=strategy_mode,
    )

    # 커버리지 확인 → 부족하면 자동 수집
    asset_codes = allocator.asset_codes()
    coverage = validate_market_data_coverage(conn, asset_codes, start, end)
    if not coverage.ok:
        import logging
        logger = logging.getLogger("uvicorn.error")
        missing = "; ".join(coverage.missing_messages)
        logger.info("[run_backtest] coverage insufficient (%s) — collecting data", missing)
        collect_for_asset_codes(conn, asset_codes, start, end)
        # 수집 후 재검증 (여전히 부족하면 엔진이 명확한 오류를 발생시킴)
        coverage = validate_market_data_coverage(conn, asset_codes, start, end)
        if not coverage.ok:
            missing = "; ".join(coverage.missing_messages)
            logger.warning("[run_backtest] coverage still incomplete after collection: %s", missing)
            raise ValueError(f"시장 데이터 수집 후에도 데이터가 부족합니다: {missing}")

    result = BacktestEngine(conn, allocator=allocator).run(
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

    cur = conn.execute("""
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
    conn.executemany("""
        INSERT INTO backtest_points
        (run_id, point_date, portfolio_value, drawdown)
        VALUES (?, ?, ?, ?)
    """, [
        (run_id, point.point_date.isoformat(), point.portfolio_value, point.drawdown)
        for point in result.points
    ])
    conn.executemany("""
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
    conn.executemany("""
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
        decision_cur = conn.execute("""
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
        conn.executemany("""
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
    conn.commit()
    return get_backtest_run(conn, run_id)


def list_backtest_runs(
    conn: sqlite3.Connection,
    limit: int = 20,
) -> list[BacktestRunResponse]:
    bounded_limit = max(1, min(int(limit or 20), 100))
    rows = conn.execute("""
        SELECT id FROM backtest_runs
        ORDER BY created_at DESC, id DESC
        LIMIT ?
    """, (bounded_limit,)).fetchall()
    return [get_backtest_run(conn, int(row["id"])) for row in rows]


def get_backtest_run(
    conn: sqlite3.Connection,
    run_id: int,
) -> BacktestRunResponse:
    row = conn.execute("SELECT * FROM backtest_runs WHERE id=?", (run_id,)).fetchone()
    if not row:
        raise KeyError(f"backtest run {run_id} not found")
    point_rows = conn.execute("""
        SELECT point_date, portfolio_value, drawdown
        FROM backtest_points
        WHERE run_id=?
        ORDER BY point_date ASC, id ASC
    """, (run_id,)).fetchall()
    position_rows = conn.execute("""
        SELECT point_date, asset_code, quantity, price, fx_rate, market_value, weight
        FROM backtest_positions
        WHERE run_id=?
        ORDER BY point_date ASC, id ASC
    """, (run_id,)).fetchall()
    trade_rows = conn.execute("""
        SELECT trade_date, asset_code, side, quantity, price, fx_rate,
               gross_amount, fee, slippage, tax, net_amount, reason
        FROM backtest_trades
        WHERE run_id=?
        ORDER BY trade_date ASC, id ASC
    """, (run_id,)).fetchall()
    decision_rows = conn.execute("""
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


def get_backtest_positions(
    conn: sqlite3.Connection,
    run_id: int,
) -> list[BacktestPosition]:
    _ensure_backtest_run(conn, run_id)
    rows = conn.execute("""
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


def get_backtest_trades(
    conn: sqlite3.Connection,
    run_id: int,
) -> list[BacktestTrade]:
    _ensure_backtest_run(conn, run_id)
    rows = conn.execute("""
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


def get_backtest_decisions(
    conn: sqlite3.Connection,
    run_id: int,
) -> list[BacktestDecision]:
    _ensure_backtest_run(conn, run_id)
    rows = conn.execute("""
        SELECT decision_date, strategy_mode, risk_profile, universe_id,
               macro_regime, macro_score, bucket_weights_json,
               final_weights_json, bottleneck_scores_json, reasons_json
        FROM backtest_decisions
        WHERE run_id=?
        ORDER BY decision_date ASC, id ASC
    """, (run_id,)).fetchall()
    return [_backtest_decision_from_row(row) for row in rows]


def _ensure_backtest_run(conn: sqlite3.Connection, run_id: int) -> None:
    row = conn.execute("SELECT 1 FROM backtest_runs WHERE id=?", (run_id,)).fetchone()
    if not row:
        raise KeyError(f"backtest run {run_id} not found")


def _backtest_decision_from_row(row) -> BacktestDecision:
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


def _portfolio_total_from_holdings(conn: sqlite3.Connection) -> float:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(h.market_value), 0) AS total
        FROM holdings h
        JOIN accounts a ON a.id = h.account_id
        WHERE COALESCE(a.include_in_rebalancing, 1) = 1
        """
    ).fetchone()
    return float(row["total"] or 0)


def _insert_order_log(
    conn: sqlite3.Connection,
    *,
    draft_id: int,
    mode: TradingMode,
    event: str,
    status: str,
    message: str,
) -> None:
    conn.execute(
        """
        INSERT INTO order_logs (draft_id, mode, event, status, message)
        VALUES (?, ?, ?, ?, ?)
        """,
        (draft_id, mode.value, event, status, message),
    )


def _order_draft_response(
    conn: sqlite3.Connection,
    draft_id: int,
    message: str | None = None,
) -> OrderDraftResponse:
    draft = conn.execute("SELECT * FROM order_drafts WHERE id=?", (draft_id,)).fetchone()
    rows = conn.execute(
        """
        SELECT * FROM order_items
        WHERE draft_id=?
        ORDER BY id
        """,
        (draft_id,),
    ).fetchall()
    items = [
        OrderItem(
            id=row["id"],
            draftId=row["draft_id"],
            accountId=row["account_id"],
            assetClass=row["asset_class"],
            side=row["side"],
            amount=row["amount"],
            status=row["status"],
            reason=row["reason"],
            createdAt=row["created_at"],
        )
        for row in rows
    ]
    return OrderDraftResponse(
        ok=True,
        draftId=draft["id"],
        mode=TradingMode(draft["mode"]),
        source=draft["source"],
        status=draft["status"],
        totalAmount=draft["total_amount"] or 0,
        itemCount=len(items),
        items=items,
        message=message,
    )


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
        mode=TradingMode(row["mode"]),
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


def get_allocation_from_holdings(conn: sqlite3.Connection) -> List[AllocationItem]:
    """실제 holdings 에서 자산군별 비중 계산"""
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


# 심볼 → 표시명 매핑
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

def get_top_movers_from_db(conn: sqlite3.Connection) -> List[TopMover]:
    """indicators 테이블에서 최근 2일 데이터로 등락률 계산"""
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


def get_calendar_events(conn: sqlite3.Connection, from_date: Optional[str] = None, to_date: Optional[str] = None) -> List[CalendarEvent]:
    try:
        where_clauses = ["event_date >= date('now')"]
        params: list = []
        if from_date:
            where_clauses = ["event_date >= ?"]
            params.append(from_date)
        if to_date:
            where_clauses.append("event_date <= ?")
            params.append(to_date)
        where_sql = " AND ".join(where_clauses)
        rows = conn.execute(f"""
            SELECT id, event_date, event_time, event_name, country
            FROM economic_events
            WHERE {where_sql}
            ORDER BY event_date, event_time
            LIMIT 50
        """, params).fetchall()
    except sqlite3.OperationalError:
        rows = []
    return [
        CalendarEvent(
            id=r["id"], date=r["event_date"], time=r["event_time"],
            title=r["event_name"], country=r["country"], importance="medium",
        )
        for r in rows
    ]


def build_insights(macro: list, kpi: KPISummary) -> Insights:
    """실제 매크로 지표값을 분석하여 동적 인사이트 생성"""
    def _find(keys: list[str]) -> float | None:
        for k in keys:
            m = next((i for i in macro if i.key == k), None)
            if m is not None:
                return m.value
        return None

    cpi      = _find(["CPIAUCSL", "cpi"])
    rate     = _find(["FEDFUNDS", "interest"])
    vix      = _find(["VIXCLS", "vix"])
    usd_krw  = _find(["USD_KRW", "exchange_usd"])
    dgs10    = _find(["DGS10"])
    t10y2y   = _find(["T10Y2Y"])

    # ── 매크로 요약 ────────────────────────────────────────────
    macro_parts: list[str] = []
    if cpi is not None:
        if cpi >= 4.0:
            macro_parts.append(f"CPI {cpi:.1f}% — 물가 상승 압력 지속")
        elif cpi >= 2.5:
            macro_parts.append(f"CPI {cpi:.1f}% — 물가 둔화 중, 목표(2%) 상회")
        else:
            macro_parts.append(f"CPI {cpi:.1f}% — 물가 안정 수준")
    if rate is not None:
        if rate >= 5.0:
            macro_parts.append(f"기준금리 {rate:.2f}% — 긴축 기조 유지")
        elif rate >= 3.0:
            macro_parts.append(f"기준금리 {rate:.2f}% — 중립 수준")
        else:
            macro_parts.append(f"기준금리 {rate:.2f}% — 완화 기조")
    if usd_krw is not None:
        macro_parts.append(f"USD/KRW {usd_krw:,.0f}원")
    macro_summary = ". ".join(macro_parts) + "." if macro_parts else "매크로 데이터를 불러오는 중입니다."

    # ── 시장 위험도 ────────────────────────────────────────────
    if vix is not None:
        if vix >= 30:
            risk = f"VIX {vix:.1f} — 시장 변동성 매우 높음 ⚠️"
        elif vix >= 20:
            risk = f"VIX {vix:.1f} — 시장 변동성 보통"
        else:
            risk = f"VIX {vix:.1f} — 시장 안정 구간"
    elif t10y2y is not None:
        if t10y2y < 0:
            risk = f"장단기 금리 역전({t10y2y:.2f}%) — 경기 침체 신호 주의"
        else:
            risk = f"장단기 스프레드 {t10y2y:.2f}% — 정상 구간"
    else:
        risk = "시장 위험 지표 데이터 없음"

    # ── 포트폴리오 요약 ────────────────────────────────────────
    if kpi.totalAssets > 0:
        port_summary = f"총자산 {kpi.totalAssets:,.0f}원, 전일 대비 {kpi.todayProfitRate:+.2f}% 변동."
    else:
        port_summary = "포트폴리오 데이터가 없습니다. 계좌/보유종목을 등록해 주세요."

    # ── 권고사항 ───────────────────────────────────────────────
    recs: list[str] = []
    if vix is not None and vix >= 25:
        recs.append("변동성 확대 구간 — 현금 비중 유지 또는 확대 검토")
    if cpi is not None and cpi >= 3.5:
        recs.append("물가 상승 지속 — 실물자산(원자재·TIPS) 비중 확인")
    if usd_krw is not None and usd_krw >= 1380:
        recs.append("고환율 구간 — 해외주식 환헤지 여부 점검")
    if dgs10 is not None and dgs10 >= 4.5:
        recs.append("미국 장기금리 고수준 — 채권 비중 재검토")
    if not recs:
        recs.append("목표 비중 유지 여부를 점검하고 리밸런싱 신호를 확인하세요")
    recommendation = ". ".join(recs) + "."

    return Insights(
        macroSummary=macro_summary,
        portfolioSummary=port_summary,
        marketRisk=risk,
        recommendation=recommendation,
    )


def get_indicator_history(conn: sqlite3.Connection, indicator: str, days: int = 180) -> list:
    """특정 지표의 히스토리 반환 (chart용)"""
    rows = conn.execute("""
        SELECT date, value FROM indicators
        WHERE indicator = ?
        ORDER BY date ASC
        LIMIT ?
    """, (indicator, days)).fetchall()
    return [{"date": r["date"], "value": r["value"]} for r in rows]
