# strategies/golden_cross.py
# SMA5/SMA20 골든크로스·데드크로스 기반 매매 신호
from .base import BaseStrategy


class GoldenCrossStrategy(BaseStrategy):
    """
    골든크로스 / 데드크로스 전략
    - SMA5 > SMA20 → 상승 추세 → BUY 신호
    - SMA5 < SMA20 → 하락 추세 → SELL 신호
    """

    name = "golden_cross"

    def generate(self, features: dict) -> dict | None:
        ma_signal = features.get("ma_signal")
        sma5  = features.get("sma5")
        sma20 = features.get("sma20")

        if ma_signal is None or sma5 is None or sma20 is None:
            return None

        # 골든크로스/데드크로스 신호만 발생 (NEUTRAL 제외)
        if ma_signal == "GOLDEN_CROSS":
            gap_pct = round((sma5 - sma20) / sma20 * 100, 2)
            confidence = min(0.5 + abs(gap_pct) / 10, 0.9)
            return {
                "indicator":   features["indicator"],
                "signal_type": "BUY",
                "strategy":    self.name,
                "confidence":  round(confidence, 4),
                "price":       features.get("latest"),
                "detail":      f"골든크로스: SMA5({sma5:.2f}) > SMA20({sma20:.2f}), 괴리율 {gap_pct:+.2f}%",
            }
        elif ma_signal == "DEAD_CROSS":
            gap_pct = round((sma5 - sma20) / sma20 * 100, 2)
            confidence = min(0.5 + abs(gap_pct) / 10, 0.9)
            return {
                "indicator":   features["indicator"],
                "signal_type": "SELL",
                "strategy":    self.name,
                "confidence":  round(confidence, 4),
                "price":       features.get("latest"),
                "detail":      f"데드크로스: SMA5({sma5:.2f}) < SMA20({sma20:.2f}), 괴리율 {gap_pct:+.2f}%",
            }
        return None
