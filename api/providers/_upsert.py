from __future__ import annotations

import sqlite3

from api.brokers.kis.models import KISBalanceSnapshot


def upsert_kis_snapshot(
    conn: sqlite3.Connection,
    *,
    snapshot: KISBalanceSnapshot,
    account_name: str,
    account_type: str,
    data_source: str,
    trade_status: str,
) -> int:
    now = conn.execute("SELECT datetime('now','localtime')").fetchone()[0]
    existing = conn.execute(
        """
        SELECT id FROM accounts
        WHERE broker='KIS' AND data_source=? AND name=?
        ORDER BY id LIMIT 1
        """,
        (data_source, account_name),
    ).fetchone()

    if existing:
        account_id = int(existing["id"])
        conn.execute(
            """
            UPDATE accounts
            SET type=?, account_type=?, initial_value=?, connection_status='CONNECTED',
                trade_status=?, last_synced_at=?
            WHERE id=?
            """,
            (account_type, account_type, snapshot.total_value, trade_status, now, account_id),
        )
    else:
        cur = conn.execute(
            """
            INSERT INTO accounts
            (name, type, account_type, broker, initial_value, connection_status,
             trade_status, include_in_rebalancing, data_source, last_synced_at)
            VALUES (?, ?, ?, 'KIS', ?, 'CONNECTED', ?, 1, ?, ?)
            """,
            (account_name, account_type, account_type, snapshot.total_value, trade_status, data_source, now),
        )
        account_id = int(cur.lastrowid)

    conn.execute("DELETE FROM holdings WHERE account_id=?", (account_id,))
    for position in snapshot.positions:
        conn.execute(
            """
            INSERT INTO holdings
            (account_id, ticker, name, quantity, avg_price, current_price,
             market_value, profit, asset_class, price, value, strategy_bucket, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'BROKER_SYNC', ?)
            """,
            (
                account_id,
                position.code,
                position.name,
                position.quantity,
                position.avg_price,
                position.current_price,
                position.market_value,
                position.profit,
                position.asset_class,
                position.current_price,
                position.market_value,
                now,
            ),
        )

    conn.execute(
        """
        INSERT INTO account_snapshots
        (account_id, total_value, cash_value, domestic_stock_value, bond_value, etf_value, snapshot_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            account_id,
            snapshot.total_value,
            snapshot.cash_value,
            snapshot.domestic_stock_value,
            snapshot.bond_value,
            snapshot.etf_value,
            now,
        ),
    )
    conn.commit()
    return account_id
