"""Risk controls for order sizing and position limits."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PositionLimit:
    max_order_notional: float
    max_position_notional: float
    max_quantity: float | None = None


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    adjusted_qty: float
    reason: str = "ok"


class RiskManager:
    """Evaluate proposed orders against simple position and notional limits."""

    def __init__(self, limits: dict[str, PositionLimit], default_limit: PositionLimit | None = None):
        self.limits = limits
        self.default_limit = default_limit or PositionLimit(
            max_order_notional=10_000,
            max_position_notional=50_000,
        )

    def evaluate_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        current_position: float = 0,
    ) -> RiskDecision:
        if qty <= 0:
            return RiskDecision(False, 0, "quantity must be positive")
        if price <= 0:
            return RiskDecision(False, 0, "price must be positive")

        limit = self.limits.get(symbol, self.default_limit)
        adjusted_qty = min(qty, limit.max_quantity) if limit.max_quantity else qty
        max_order_qty = limit.max_order_notional / price
        if adjusted_qty > max_order_qty:
            adjusted_qty = max_order_qty

        signed_qty = adjusted_qty if side.upper() == "BUY" else -adjusted_qty
        projected_notional = abs((current_position + signed_qty) * price)
        if projected_notional > limit.max_position_notional:
            return RiskDecision(False, 0, "position limit exceeded")
        if adjusted_qty <= 0:
            return RiskDecision(False, 0, "order below risk limit")
        reason = "ok" if adjusted_qty == qty else "quantity adjusted by risk limit"
        return RiskDecision(True, adjusted_qty, reason)

