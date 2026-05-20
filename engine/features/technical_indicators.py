# transforms/technical_indicators.py
# 기술적 지표 계산 모듈
# DB indicators 테이블의 역사적 가격 데이터를 기반으로
# SMA, EMA, RSI, MACD, 볼린저 밴드 등 표준 지표를 계산합니다.
import logging
import sqlite3

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

from storage.database import DB_PATH


# ── 공통 헬퍼 ────────────────────────────────────────────────────────────────

def _load_series(indicator: str, db_path: str = DB_PATH, limit: int = 200) -> pd.Series:
    """DB에서 지표의 역사적 가격 시계열 반환 (날짜순 정렬)."""
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        """
        SELECT date, value FROM indicators
        WHERE indicator = ? AND is_stale = 0
        ORDER BY date ASC
        LIMIT ?
        """,
        conn,
        params=(indicator, limit),
    )
    conn.close()
    if df.empty:
        return pd.Series(dtype=float)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")["value"].astype(float)


# ── 이동평균 ─────────────────────────────────────────────────────────────────

def compute_sma(indicator: str, period: int = 20, db_path: str = DB_PATH) -> pd.Series:
    """단순 이동평균 (Simple Moving Average)."""
    s = _load_series(indicator, db_path)
    if len(s) < period:
        return pd.Series(dtype=float)
    return s.rolling(window=period).mean().dropna()


def compute_ema(indicator: str, period: int = 20, db_path: str = DB_PATH) -> pd.Series:
    """지수 이동평균 (Exponential Moving Average)."""
    s = _load_series(indicator, db_path)
    if len(s) < period:
        return pd.Series(dtype=float)
    return s.ewm(span=period, adjust=False).mean()


# ── RSI ──────────────────────────────────────────────────────────────────────

def compute_rsi(indicator: str, period: int = 14, db_path: str = DB_PATH) -> pd.Series:
    """
    상대강도지수 (Relative Strength Index).
    RSI > 70 → 과매수, RSI < 30 → 과매도.
    """
    s = _load_series(indicator, db_path)
    if len(s) < period + 1:
        return pd.Series(dtype=float)
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    # avg_loss=0, avg_gain>0 → RSI=100 (완전 상승); avg_gain=avg_loss=0 → RSI=50 (보합)
    rsi = rsi.where(avg_loss != 0, other=avg_gain.apply(lambda g: 100.0 if g > 0 else 50.0))
    return rsi.dropna()


# ── MACD ─────────────────────────────────────────────────────────────────────

def compute_macd(
    indicator: str,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    db_path: str = DB_PATH,
) -> dict[str, pd.Series]:
    """
    MACD 지표 계산.
    반환: {"macd": Series, "signal": Series, "histogram": Series}
    - macd > signal → 상승 모멘텀
    - histogram > 0 → 매수 우세
    """
    s = _load_series(indicator, db_path)
    if len(s) < slow + signal:
        return {"macd": pd.Series(dtype=float), "signal": pd.Series(dtype=float),
                "histogram": pd.Series(dtype=float)}
    ema_fast = s.ewm(span=fast, adjust=False).mean()
    ema_slow = s.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return {
        "macd":      macd_line.dropna(),
        "signal":    signal_line.dropna(),
        "histogram": histogram.dropna(),
    }


# ── 볼린저 밴드 ──────────────────────────────────────────────────────────────

def compute_bollinger_bands(
    indicator: str,
    period: int = 20,
    num_std: float = 2.0,
    db_path: str = DB_PATH,
) -> dict[str, pd.Series]:
    """
    볼린저 밴드 계산.
    반환: {"upper": Series, "middle": Series, "lower": Series, "bandwidth": Series}
    - 가격이 upper band 돌파 → 과매수 신호
    - 가격이 lower band 하향 → 과매도 신호
    """
    s = _load_series(indicator, db_path)
    if len(s) < period:
        empty = pd.Series(dtype=float)
        return {"upper": empty, "middle": empty, "lower": empty, "bandwidth": empty}
    middle = s.rolling(window=period).mean()
    std = s.rolling(window=period).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    bandwidth = (upper - lower) / middle * 100
    return {
        "upper":     upper.dropna(),
        "middle":    middle.dropna(),
        "lower":     lower.dropna(),
        "bandwidth": bandwidth.dropna(),
    }


# ── 복합 요약 ─────────────────────────────────────────────────────────────────

def compute_all_features(indicator: str, db_path: str = DB_PATH) -> dict:
    """
    지표에 대한 모든 기술적 지표를 계산하여 최신값 요약 딕셔너리로 반환.
    존재하지 않는 지표 → 빈 dict.
    """
    s = _load_series(indicator, db_path)
    if s.empty:
        return {}

    latest = float(s.iloc[-1])

    def _last(series):
        return round(float(series.iloc[-1]), 4) if len(series) > 0 else None

    sma5  = _last(compute_sma(indicator, 5, db_path))
    sma20 = _last(compute_sma(indicator, 20, db_path))
    ema12 = _last(compute_ema(indicator, 12, db_path))
    rsi14 = _last(compute_rsi(indicator, 14, db_path))
    macd_data = compute_macd(indicator, db_path=db_path)
    bb_data   = compute_bollinger_bands(indicator, db_path=db_path)

    result = {
        "indicator": indicator,
        "latest":    round(latest, 4),
        "sma5":      sma5,
        "sma20":     sma20,
        "ema12":     ema12,
        "rsi14":     rsi14,
        "macd":      _last(macd_data["macd"]),
        "macd_signal":   _last(macd_data["signal"]),
        "macd_hist": _last(macd_data["histogram"]),
        "bb_upper":  _last(bb_data["upper"]),
        "bb_middle": _last(bb_data["middle"]),
        "bb_lower":  _last(bb_data["lower"]),
        "bb_bandwidth": _last(bb_data["bandwidth"]),
        "n_obs":     len(s),
    }

    # 파생 신호
    if rsi14 is not None:
        if rsi14 > 70:
            result["rsi_signal"] = "OVERBOUGHT"
        elif rsi14 < 30:
            result["rsi_signal"] = "OVERSOLD"
        else:
            result["rsi_signal"] = "NEUTRAL"

    if sma5 is not None and sma20 is not None:
        if sma5 > sma20:
            result["ma_signal"] = "GOLDEN_CROSS"   # 단기 > 장기 = 상승
        else:
            result["ma_signal"] = "DEAD_CROSS"     # 단기 < 장기 = 하락

    if result.get("macd_hist") is not None:
        result["macd_bias"] = "BULLISH" if result["macd_hist"] > 0 else "BEARISH"

    logger.debug(f"[TI] {indicator}: RSI={rsi14}, MA={result.get('ma_signal')}")
    return result
