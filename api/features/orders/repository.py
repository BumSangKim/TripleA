from __future__ import annotations

import sqlite3
from typing import Any, Optional

from api.features.orders.models import OrderDraftParams, OrderExecuteParams
from api.features.orders.schemas import OrderDraftResponse, OrderItem
from api.providers.modes import TradingMode


class OrdersRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list_drafts(self, mode: Optional[Any], limit: int) -> list[OrderDraftResponse]:
        if mode:
            rows = self._conn.execute(
                """
                SELECT id FROM order_drafts
                WHERE mode=?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (mode.value, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT id FROM order_drafts
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_order_draft_response(self._conn, int(row["id"])) for row in rows]

    def create_draft(self, params: OrderDraftParams) -> OrderDraftResponse:
        mode = params.mode
        source = params.source
        max_order_amount = params.max_order_amount

        if source != "rebalancing":
            raise ValueError("Only rebalancing order drafts are supported")
        if mode not in {TradingMode.PAPER, TradingMode.LIVE}:
            raise PermissionError(f"{mode.value} mode cannot create order drafts")

        total_assets = _portfolio_total_from_holdings(self._conn)
        from api.providers.router import provider_router
        targets = [
            target for target in provider_router.get(mode).get_target_deviations(self._conn)
            if (target.target_type or "asset_allocation") == "asset_allocation" and target.level != "normal"
        ]
        status = "DRAFT"
        cur = self._conn.execute(
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
            item_cur = self._conn.execute(
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
        self._conn.execute(
            "UPDATE order_drafts SET status=?, total_amount=? WHERE id=?",
            (status, total_amount, draft_id),
        )
        _insert_order_log(
            self._conn,
            draft_id=draft_id,
            mode=mode,
            event="DRAFT_CREATED",
            status=status,
            message=f"{len(items)} order candidates generated",
        )
        self._conn.commit()
        return _order_draft_response(self._conn, draft_id, message="주문 후보가 생성되었습니다.")

    def execute_draft(self, params: OrderExecuteParams) -> OrderDraftResponse:
        mode = params.mode
        draft_id = params.order_draft_id
        confirm_text = params.confirm_text

        draft = self._conn.execute("SELECT * FROM order_drafts WHERE id=?", (draft_id,)).fetchone()
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
        self._conn.execute(
            """
            UPDATE order_drafts
            SET status=?, approved_at=datetime('now','localtime')
            WHERE id=?
            """,
            (status, draft_id),
        )
        self._conn.execute(
            "UPDATE order_items SET status=? WHERE draft_id=?",
            (status, draft_id),
        )
        _insert_order_log(
            self._conn,
            draft_id=draft_id,
            mode=mode,
            event="PAPER_APPROVED",
            status=status,
            message="Paper order draft manually approved; broker submission is not implemented yet",
        )
        self._conn.commit()
        return _order_draft_response(self._conn, draft_id, message="모의 주문 후보가 승인 로그로 기록되었습니다.")


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
