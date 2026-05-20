# engine/valuation/mispricing.py
# 고평가/저평가 스코어 계산
#
# 수식:
#   Mispricing_i = (CurrentMultiple - FairMultiple) / FairMultiple
#
#   OvervaluationScore = 0.4·Gap_EV/EBITDA + 0.3·Gap_PER + 0.3·Gap_PBR
#
#   판단 기준:
#     Score > +0.25 → 명확한 고평가
#     +0.10 ~ +0.25 → 고평가 경계
#     -0.10 ~ +0.10 → 적정
#     -0.25 ~ -0.10 → 저평가 경계
#     Score < -0.25 → 명확한 저평가

import logging
import sqlite3

import numpy as np
import pandas as pd

from storage.database import DB_PATH

logger = logging.getLogger(__name__)


def compute_mispricing(current: float, fair: float) -> float | None:
    """
    개별 멀티플 괴리율 계산.

    Parameters
    ----------
    current : 현재 시장 멀티플
    fair    : 모델 추정 적정 멀티플

    Returns
    -------
    float | None
        (current - fair) / fair
        None if inputs are invalid
    """
    if current is None or fair is None or fair <= 0 or current < 0:
        return None
    return (current - fair) / fair


def compute_overvaluation_score(
    mispricing_ev_ebitda: float | None,
    mispricing_per: float | None,
    mispricing_pbr: float | None,
) -> float | None:
    """
    복합 고평가 스코어.

    OvervaluationScore = 0.4·Gap_EV/EBITDA + 0.3·Gap_PER + 0.3·Gap_PBR

    None 입력 시 가용 지표만으로 가중 재계산.
    """
    weights = []
    values = []

    for val, w in [
        (mispricing_ev_ebitda, 0.4),
        (mispricing_per, 0.3),
        (mispricing_pbr, 0.3),
    ]:
        if val is not None and not np.isnan(float(val)):
            values.append(float(val) * w)
            weights.append(w)

    if not weights:
        return None

    # 가중치 합이 1이 되도록 재정규화
    total_w = sum(weights)
    return sum(values) / total_w


def classify_signal(score: float | None) -> str:
    """
    복합 스코어 → 투자 판단 라벨.

    Parameters
    ----------
    score : OvervaluationScore (양수 = 고평가, 음수 = 저평가)

    Returns
    -------
    str : '명확한 고평가' | '고평가 경계' | '적정' | '저평가 경계' | '명확한 저평가' | '판단불가'
    """
    if score is None:
        return "판단불가"
    if score > 0.25:
        return "명확한 고평가"
    if score > 0.10:
        return "고평가 경계"
    if score > -0.10:
        return "적정"
    if score > -0.25:
        return "저평가 경계"
    return "명확한 저평가"


def classify_short(score: float | None) -> str:
    """간략 라벨 (텔레그램 표시용): 고평가 | 적정 | 저평가"""
    if score is None:
        return "판단불가"
    if score > 0.10:
        return "고평가"
    if score > -0.10:
        return "적정"
    return "저평가"


def compute_zscore_vs_history(
    ticker: str,
    current_ev_ebitda: float,
    db_path: str = DB_PATH,
    lookback_n: int = 52,
) -> float | None:
    """
    자기 과거 대비 Z-score 계산.

    ZValuation = (CurrentMultiple - HistoricalMean) / HistoricalStd

    데이터가 부족(< 4)하면 None 반환.
    """
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT ev_ebitda FROM company_multiples "
            "WHERE ticker=? AND ev_ebitda > 0 ORDER BY date DESC LIMIT ?",
            (ticker, lookback_n),
        ).fetchall()
    finally:
        conn.close()

    if len(rows) < 4:
        return None

    values = [r[0] for r in rows]
    mean = np.mean(values)
    std = np.std(values)
    if std < 0.01:
        return None
    return (current_ev_ebitda - mean) / std


def compute_final_score(
    macro_mispricing: float | None,
    zscore_vs_history: float | None,
) -> float | None:
    """
    최종 종합 스코어.

    FinalScore = 0.5·MacroAdjustedGap(표준화) + 0.5·ZValuation(표준화)

    두 지표의 단위가 다르므로 직접 평균하면 오류. 여기서는:
    - macro_mispricing은 이미 비율 (0.2 = 20%)
    - zscore는 σ 단위
    z를 비율 스케일로 변환: z→ratio ≈ z × 0.15 (역사적 변동성 15% 가정)
    """
    parts = []
    if macro_mispricing is not None:
        parts.append(macro_mispricing)
    if zscore_vs_history is not None:
        # σ → 비율 스케일 근사 변환 (15% volatility 가정)
        parts.append(zscore_vs_history * 0.15)
    if not parts:
        return None
    return sum(parts) / len(parts)


def summarize_valuation_table(db_path: str = DB_PATH) -> pd.DataFrame:
    """
    최신 밸류에이션 결과를 읽기 좋은 형태로 정리.

    Returns
    -------
    pd.DataFrame with columns:
        ticker, sector, current_ev_ebitda, fair_ev_ebitda,
        mispricing_pct, signal, model_type
    """
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(
            """
            SELECT v.ticker, v.sector,
                   ROUND(v.current_ev_ebitda, 1) as current_ev_ebitda,
                   ROUND(v.fair_ev_ebitda, 1)    as fair_ev_ebitda,
                   ROUND(v.mispricing_ev_ebitda * 100, 1) as mispricing_pct,
                   ROUND(v.current_per, 1) as current_per,
                   ROUND(v.fair_per, 1)    as fair_per,
                   ROUND(v.overvaluation_score * 100, 1) as overvaluation_score_pct,
                   v.valuation_signal as signal,
                   v.model_type,
                   v.date
            FROM valuation_results v
            INNER JOIN (
                SELECT ticker, MAX(date) as max_date
                FROM valuation_results GROUP BY ticker
            ) latest ON v.ticker=latest.ticker AND v.date=latest.max_date
            ORDER BY v.overvaluation_score DESC
            """,
            conn,
        )
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df
