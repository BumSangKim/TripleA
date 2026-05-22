"""
api/services.py
비즈니스 로직 - 리밸런싱 계산, 데이터 조합
"""
from __future__ import annotations
import sqlite3
from typing import List, Optional
from .models import (
    MacroIndicator, TargetItem, SuggestionItem, AlertItem,
    KPISummary, AllocationItem, AccountSummary, TopMover, CalendarEvent, Insights,
    AccountPolicyItem, AccountSnapshotCreate, AccountSnapshotItem,
    RebalanceResultItem, OrderDraftResponse, OrderItem,
)
from .modes import TradingMode

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
    # 기타 목표: mock 현재 값
    mock_special = {
        "월 투자 목표":   8_200_000,  # 원
        "연 수익률 목표": 5.2,         # %
    }

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
            curr = mock_special.get(t["asset_class"], target_val * 0.8)
            unit = "원"
        elif t_type == "return_rate":
            curr = mock_special.get(t["asset_class"], target_val * 0.65)
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


def record_rebalance_results(
    conn: sqlite3.Connection,
    mode: TradingMode,
    targets: list[TargetItem],
    total_assets: float,
) -> tuple[int, list[RebalanceResultItem]]:
    run_id = int(conn.execute("SELECT strftime('%s','now')").fetchone()[0])
    rows: list[RebalanceResultItem] = []
    for target in targets:
        action, reason = _rebalance_action_reason(target)
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
    # USD/KRW 실제값 반영
    usd_krw = next((i.value for i in macro if "KRW" in (i.unit or "") or "USD_KRW" in (i.key or "")), None)
    krw_str = f" (USD/KRW {usd_krw:,.0f})" if usd_krw else ""
    return Insights(
        macroSummary=f"물가 상승률이 둔화되고 있으며 금리 인상 속도가 완화될 전망입니다.{krw_str}",
        portfolioSummary=f"총자산은 전일 대비 {kpi.todayProfitRate:+.2f}% 변동했습니다." if kpi.totalAssets > 0
                         else "포트폴리오 데이터가 없습니다. 계좌/보유종목을 등록해 주세요.",
        marketRisk="현재 시장 위험도는 보통 수준입니다.",
        recommendation="매크로 지표를 점검하고 목표 비중 유지 여부를 확인하십시오.",
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
