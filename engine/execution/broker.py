"""Broker client abstractions and a paper-trading implementation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from itertools import count


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str
    qty: float
    price: float | None = None
    order_type: str = "market"
    strategy: str | None = None
    signal_id: int | None = None


@dataclass(frozen=True)
class OrderResult:
    order_id: str
    symbol: str
    side: str
    qty: float
    price: float | None
    status: str
    broker: str
    submitted_at: str
    reason: str | None = None

    def as_record(self) -> dict:
        return {
            "broker_order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "qty": self.qty,
            "price": self.price,
            "status": self.status,
            "broker": self.broker,
            "reason": self.reason,
        }


class BrokerClient(ABC):
    """Interface for real or paper broker implementations."""

    name = "broker"

    @abstractmethod
    def place_order(self, symbol: str, side: str, qty: float, price: float | None = None) -> OrderResult:
        ...

    def get_account_balance(self) -> dict:
        return {}


class PaperBrokerClient(BrokerClient):
    """In-memory broker for local development and tests."""

    name = "paper"

    def __init__(self):
        self._ids = count(1)
        self.orders: list[OrderResult] = []

    def place_order(self, symbol: str, side: str, qty: float, price: float | None = None) -> OrderResult:
        result = OrderResult(
            order_id=f"PAPER-{next(self._ids)}",
            symbol=symbol,
            side=side.upper(),
            qty=float(qty),
            price=price,
            status="filled",
            broker=self.name,
            submitted_at=datetime.now().isoformat(timespec="seconds"),
        )
        self.orders.append(result)
        return result

