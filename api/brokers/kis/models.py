from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KISPosition:
    code: str
    name: str
    quantity: float
    avg_price: float
    current_price: float
    market_value: float
    profit: float
    asset_class: str = "국내주식"


@dataclass(frozen=True)
class KISBalanceSnapshot:
    account_masked: str
    total_value: float
    cash_value: float
    domestic_stock_value: float
    positions: list[KISPosition]
    bond_value: float = 0
    etf_value: float = 0
    message: str = ""
