"""Order execution orchestration."""

from storage.database import DB_PATH, record_order
from engine.execution.broker import BrokerClient, OrderRequest, OrderResult
from engine.risk.manager import RiskManager


class OrderExecutor:
    """Apply risk checks, submit orders to a broker, and persist results."""

    def __init__(self, broker: BrokerClient, risk_manager: RiskManager, db_path: str = DB_PATH):
        self.broker = broker
        self.risk_manager = risk_manager
        self.db_path = db_path

    def place_order(self, request: OrderRequest, current_position: float = 0) -> OrderResult:
        price = request.price or 0
        decision = self.risk_manager.evaluate_order(
            symbol=request.symbol,
            side=request.side,
            qty=request.qty,
            price=price,
            current_position=current_position,
        )
        if not decision.allowed:
            result = OrderResult(
                order_id="REJECTED",
                symbol=request.symbol,
                side=request.side.upper(),
                qty=0,
                price=request.price,
                status="rejected",
                broker=self.broker.name,
                submitted_at="",
                reason=decision.reason,
            )
        else:
            result = self.broker.place_order(
                request.symbol,
                request.side,
                decision.adjusted_qty,
                request.price,
            )
            if decision.reason != "ok":
                result = OrderResult(**{**result.__dict__, "reason": decision.reason})

        record = result.as_record()
        record["strategy"] = request.strategy
        record["signal_id"] = request.signal_id
        record_order(record, db_path=self.db_path)
        return result

