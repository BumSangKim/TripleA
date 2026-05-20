# strategies/base.py
# 모든 전략의 기반 클래스
from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    """매매 신호 생성 전략 기반 클래스."""

    name: str = "base"

    @abstractmethod
    def generate(self, features: dict) -> dict | None:
        """
        기술적 지표 피처 딕셔너리에서 신호를 생성한다.
        신호가 발생하면 dict 반환, 신호 없으면 None 반환.
        반환 dict 형식:
          {
            "indicator":   str,   # 지표 이름 (예: "KOSPI")
            "signal_type": str,   # "BUY" | "SELL" | "HOLD"
            "strategy":    str,   # 전략 이름
            "confidence":  float, # 0.0 ~ 1.0
            "price":       float | None,  # 현재가 (latest)
            "detail":      str,   # 한국어 설명
          }
        """
