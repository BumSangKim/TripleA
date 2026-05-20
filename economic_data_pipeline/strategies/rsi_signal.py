# strategies/rsi_signal.py
# RSI 과매수/과매도 기반 역추세 신호
from .base import BaseStrategy


class RSISignalStrategy(BaseStrategy):
    """
    RSI 14 기반 역추세 전략
    - RSI > 70 → 과매수 → SELL 신호 (조정 예상)
    - RSI < 30 → 과매도 → BUY  신호 (반등 예상)
    - 30 ≤ RSI ≤ 70 → 중립, 신호 없음
    """

    name = "rsi_signal"

    OVERBOUGHT = 70.0
    OVERSOLD   = 30.0

    def generate(self, features: dict) -> dict | None:
        rsi14 = features.get("rsi14")
        if rsi14 is None:
            return None

        if rsi14 > self.OVERBOUGHT:
            extreme = round((rsi14 - self.OVERBOUGHT) / 30, 4)
            confidence = round(min(0.5 + extreme, 0.95), 4)
            return {
                "indicator":   features["indicator"],
                "signal_type": "SELL",
                "strategy":    self.name,
                "confidence":  confidence,
                "price":       features.get("latest"),
                "detail":      f"과매수: RSI14={rsi14:.1f} (기준 {self.OVERBOUGHT})",
            }
        elif rsi14 < self.OVERSOLD:
            extreme = round((self.OVERSOLD - rsi14) / 30, 4)
            confidence = round(min(0.5 + extreme, 0.95), 4)
            return {
                "indicator":   features["indicator"],
                "signal_type": "BUY",
                "strategy":    self.name,
                "confidence":  confidence,
                "price":       features.get("latest"),
                "detail":      f"과매도: RSI14={rsi14:.1f} (기준 {self.OVERSOLD})",
            }
        return None
