# strategies/__init__.py
# 매매 신호 생성 전략 모음
from .golden_cross import GoldenCrossStrategy
from .rsi_signal import RSISignalStrategy
from .macd_signal import MACDSignalStrategy

_STRATEGIES = [GoldenCrossStrategy, RSISignalStrategy, MACDSignalStrategy]

# 기술적 지표를 계산할 주요 지표 목록 (indicators 테이블 key)
DEFAULT_INDICATORS = [
    "KOSPI",
    "KOSDAQ",
    "GOLD",
    "WTI",
    "USD_KRW",
    "US500",
    "SMH",
    "SPY",
]


def run_all_strategies(
    indicators: list[str] = None,
    db_path: str = "economic_data.db",
) -> list[dict]:
    """
    모든 전략을 지정된 지표에 대해 실행 후 생성된 신호 목록을 반환한다.
    각 신호: {"indicator", "signal_type", "strategy", "confidence", "price", "detail"}
    """
    from transforms.technical_indicators import compute_all_features

    targets = indicators or DEFAULT_INDICATORS
    all_signals: list[dict] = []

    for ind in targets:
        features = compute_all_features(ind, db_path)
        if not features:
            continue
        for StrategyClass in _STRATEGIES:
            strategy = StrategyClass()
            sig = strategy.generate(features)
            if sig:
                all_signals.append(sig)

    return all_signals
