from __future__ import annotations

from dataclasses import dataclass


LABELS = {"BENIGN", "ADAPTIVE_TRANSITION", "STRESS", "CRASH", "RECOVERY", "TREND_EXPANSION", "CHOPPY_NOISE", "UNKNOWN"}


@dataclass(frozen=True)
class RealizedRegimeLabel:
    label: str
    future_return: float
    future_max_drawdown: float
    realized_volatility: float
    reason_codes: list[str]


class RealizedRegimeLabeler:
    def label(self, prices: list[float]) -> RealizedRegimeLabel:
        if len(prices) < 5 or prices[0] <= 0:
            return RealizedRegimeLabel("UNKNOWN", 0.0, 0.0, 0.0, ["insufficient_future_data"])
        future_return = prices[-1] / prices[0] - 1
        peak = prices[0]
        max_drawdown = 0.0
        for price in prices:
            peak = max(peak, price)
            max_drawdown = min(max_drawdown, price / peak - 1)
        returns = [prices[i] / prices[i - 1] - 1 for i in range(1, len(prices)) if prices[i - 1] > 0]
        vol = (sum((r - sum(returns) / len(returns)) ** 2 for r in returns) / len(returns)) ** 0.5 if returns else 0.0
        if max_drawdown <= -0.30:
            label = "CRASH"
        elif max_drawdown <= -0.12:
            label = "RECOVERY" if future_return > 0 else "STRESS"
        elif future_return > 0.10 and vol < 0.05:
            label = "TREND_EXPANSION"
        elif abs(future_return) < 0.03 and vol < 0.03:
            label = "BENIGN"
        else:
            label = "CHOPPY_NOISE"
        return RealizedRegimeLabel(label, future_return, max_drawdown, vol, [f"label:{label}"])
