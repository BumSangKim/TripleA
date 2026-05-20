# strategies/macd_signal.py
# MACD 히스토그램 방향 전환 기반 신호
from .base import BaseStrategy


class MACDSignalStrategy(BaseStrategy):
    """
    MACD 바이어스 기반 모멘텀 전략
    - MACD 히스토그램 > 0 (상승 모멘텀) → BUY 신호
    - MACD 히스토그램 < 0 (하락 모멘텀) → SELL 신호
    - 신뢰도는 히스토그램 절대값에 따라 조정
    """

    name = "macd_signal"
    MIN_CONFIDENCE = 0.52   # 최소 신뢰도 미달 시 신호 미발생 (rel > 0.04% 필요)
    HIST_SCALE    = 0.01    # 히스토그램 값 → 신뢰도 보정 계수

    def generate(self, features: dict) -> dict | None:
        macd_hist = features.get("macd_hist")
        macd_bias = features.get("macd_bias")
        if macd_hist is None or macd_bias is None:
            return None

        abs_hist = abs(macd_hist)
        latest = features.get("latest") or 1.0
        # 히스토그램을 현재가 대비 비율로 정규화하여 신뢰도 계산
        rel = abs_hist / max(abs(latest), 1.0)
        confidence = round(min(0.5 + rel * 50, 0.90), 4)

        if confidence < self.MIN_CONFIDENCE:
            return None

        if macd_bias == "BULLISH":
            return {
                "indicator":   features["indicator"],
                "signal_type": "BUY",
                "strategy":    self.name,
                "confidence":  confidence,
                "price":       features.get("latest"),
                "detail":      f"MACD 상승모멘텀: histogram={macd_hist:.4f} (MACD={features.get('macd'):.4f})",
            }
        else:  # BEARISH
            return {
                "indicator":   features["indicator"],
                "signal_type": "SELL",
                "strategy":    self.name,
                "confidence":  confidence,
                "price":       features.get("latest"),
                "detail":      f"MACD 하락모멘텀: histogram={macd_hist:.4f} (MACD={features.get('macd'):.4f})",
            }
