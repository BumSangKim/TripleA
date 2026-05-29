from __future__ import annotations

import sqlite3

_POLICIES = [
    ("GENERAL", "SATELLITE", "입출금 자유", "국내/해외 주식, ETF 등", "공격 기회 활용", "단기 유동성 관리"),
    ("ISA", "TAX_ADVANTAGED", "연간 납입 한도 고려", "국내 상장 상품 중심", "신규 납입금 활용 우선", "잦은 매매 자제"),
    ("PENSION_SAVINGS", "RETIREMENT", "장기 납입", "연금 계좌 허용 상품", "방어형 장기 운용", "위험자산 과다 노출 제한"),
    ("IRP", "RETIREMENT", "출금 제약", "IRP 허용 상품", "안전자산 우선", "안전자산 비중 유지"),
]


def seed(conn: sqlite3.Connection) -> None:
    conn.executemany("""
        INSERT INTO account_policies
        (account_type, role, deposit_policy, allowed_products, rebalance_priority, risk_note)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(account_type) DO UPDATE SET
            role=excluded.role,
            deposit_policy=excluded.deposit_policy,
            allowed_products=excluded.allowed_products,
            rebalance_priority=excluded.rebalance_priority,
            risk_note=excluded.risk_note,
            updated_at=datetime('now','localtime')
    """, _POLICIES)
