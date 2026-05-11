# preprocessor.py
# 수집 데이터 정제 및 통계 지표 산출
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


def clean_series(df: pd.DataFrame, value_col: str = "value") -> pd.DataFrame:
    """
    결측치·이상치 처리
    1) 결측치: 직전값으로 선형보간
    2) 이상치: 3σ 초과값은 경계값으로 대체(winsorize)
    """
    df = df.copy().sort_values("date").reset_index(drop=True)
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")

    # 1. 결측치 보간
    df[value_col] = df[value_col].interpolate(method="linear").ffill().bfill()

    # 2. 이상치 처리 (3σ 룰) - 데이터가 충분할 때만 적용
    if len(df) >= 5:
        mean = df[value_col].mean()
        std = df[value_col].std()
        if std > 0:
            lower, upper = mean - 3 * std, mean + 3 * std
            outliers = (df[value_col] < lower) | (df[value_col] > upper)
            if outliers.any():
                logger.warning(f"이상치 {outliers.sum()}건 감지 → 경계값으로 대체")
                df.loc[df[value_col] < lower, value_col] = lower
                df.loc[df[value_col] > upper, value_col] = upper

    return df


def compute_stats(df: pd.DataFrame, value_col: str = "value") -> dict:
    """이동평균, 변동성, 전일/전월 변화율 산출"""
    s = df[value_col].astype(float)
    n = len(s)
    return {
        "latest":     round(float(s.iloc[-1]), 4) if n > 0 else None,
        "prev":       round(float(s.iloc[-2]), 4) if n > 1 else None,
        "change_pct": round((float(s.iloc[-1]) / float(s.iloc[-2]) - 1) * 100, 2)
                      if n > 1 and s.iloc[-2] != 0 else None,
        "ma5":        round(float(s.rolling(5).mean().iloc[-1]), 4)  if n >= 5  else None,
        "ma20":       round(float(s.rolling(20).mean().iloc[-1]), 4) if n >= 20 else None,
        "volatility": round(float(s.rolling(20).std().iloc[-1]), 4)  if n >= 20 else None,
    }


def detect_changepoint(df: pd.DataFrame, value_col: str = "value") -> list:
    """
    ruptures 라이브러리를 사용한 변화점 탐지
    반환: 변화점 인덱스 목록 (설치 안 된 경우 빈 리스트)
    """
    try:
        import ruptures as rpt
        signal = df[value_col].astype(float).values
        if len(signal) < 10:
            return []
        algo = rpt.Pelt(model="rbf").fit(signal)
        breakpoints = algo.predict(pen=10)
        return breakpoints[:-1]  # 마지막 원소(len) 제외
    except ImportError:
        logger.debug("ruptures 미설치: 변화점 탐지 생략")
        return []
    except Exception as e:
        logger.warning(f"변화점 탐지 실패: {e}")
        return []
