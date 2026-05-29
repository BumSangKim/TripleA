from __future__ import annotations

import sqlite3
from typing import Any

from api.features.accounts.schemas import (
    AccountPolicyItem,
    AccountSnapshotCreate,
    AccountSnapshotItem,
    AccountSummary,
    AllocationItem,
)


class AccountsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_accounts(self, mode: Any) -> list[AccountSummary]:
        from api.providers.router import provider_router
        return provider_router.get(mode).get_accounts(self._conn)

    def get_account_policies(self) -> list[AccountPolicyItem]:
        rows = self._conn.execute("""
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

    def get_snapshots(self, account_id: int, limit: int) -> list[AccountSnapshotItem]:
        rows = self._conn.execute("""
            SELECT * FROM account_snapshots
            WHERE account_id=?
            ORDER BY snapshot_at DESC, id DESC
            LIMIT ?
        """, (account_id, limit)).fetchall()
        return [_snapshot_from_row(r) for r in rows]

    def save_manual_snapshot(self, account_id: int, body: AccountSnapshotCreate) -> AccountSnapshotItem:
        account = self._conn.execute("SELECT id FROM accounts WHERE id=?", (account_id,)).fetchone()
        if not account:
            raise KeyError(f"account {account_id} not found")

        snapshot_at = body.snapshotAt or self._conn.execute(
            "SELECT datetime('now','localtime')"
        ).fetchone()[0]
        cur = self._conn.execute("""
            INSERT INTO account_snapshots
            (account_id, total_value, cash_value, domestic_stock_value, foreign_stock_value,
             bond_value, etf_value, pension_value, alt_value, snapshot_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            account_id,
            body.totalValue,
            body.cashValue,
            body.domesticStockValue,
            body.foreignStockValue,
            body.bondValue,
            body.etfValue,
            body.pensionValue,
            body.altValue,
            snapshot_at,
        ))
        self._conn.execute("""
            UPDATE accounts
            SET initial_value=?,
                data_source='MANUAL',
                connection_status='UNLINKED',
                last_synced_at=?
            WHERE id=?
        """, (body.totalValue, snapshot_at, account_id))
        self._conn.commit()

        row = self._conn.execute(
            "SELECT * FROM account_snapshots WHERE id=?", (cur.lastrowid,)
        ).fetchone()
        return _snapshot_from_row(row)

    def set_rebalancing_inclusion(self, account_id: int, include: bool) -> bool:
        cur = self._conn.execute(
            "UPDATE accounts SET include_in_rebalancing=? WHERE id=?",
            (1 if include else 0, account_id),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def upsert_holdings_from_rows(self, rows: list[dict]) -> int:
        inserted = 0
        for row in rows:
            acct_name = row.get("account_name", "업로드 계좌").strip()
            existing = self._conn.execute(
                "SELECT id FROM accounts WHERE name=?", (acct_name,)
            ).fetchone()
            if existing:
                account_id = existing["id"]
            else:
                cur = self._conn.execute(
                    """
                    INSERT INTO accounts
                    (name, type, account_type, connection_status, data_source)
                    VALUES (?, '일반', 'GENERAL', 'UNLINKED', 'CSV')
                    """,
                    (acct_name,),
                )
                account_id = cur.lastrowid

            ticker = row["ticker"].strip()
            qty = float(row["quantity"])
            avg_p = float(row["avg_price"])
            cur_p = float(row["current_price"])
            market_value = qty * cur_p
            profit = (cur_p - avg_p) * qty

            existing_h = self._conn.execute(
                "SELECT id FROM holdings WHERE account_id=? AND ticker=?",
                (account_id, ticker),
            ).fetchone()
            if existing_h:
                self._conn.execute(
                    """
                    UPDATE holdings SET quantity=?, avg_price=?, current_price=?,
                    market_value=?, profit=?, updated_at=datetime('now','localtime')
                    WHERE id=?
                    """,
                    (qty, avg_p, cur_p, market_value, profit, existing_h["id"]),
                )
            else:
                self._conn.execute(
                    """
                    INSERT INTO holdings
                    (account_id, ticker, name, quantity, avg_price, current_price, market_value, profit)
                    VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (account_id, ticker, row["name"].strip(), qty, avg_p, cur_p, market_value, profit),
                )
            inserted += 1
        self._conn.commit()
        return inserted

    def get_allocation(self) -> list[AllocationItem]:
        rows = self._conn.execute("""
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
