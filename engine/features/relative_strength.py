# transforms/relative_strength.py
# 섹터 상대강도(Relative Strength) 계산
# SMH/SPY: 반도체 vs 시장, XLU/SPY: 유틸리티(전력) vs 시장
#
# 상대강도 = 분자 지표 최신가 / 분모 지표 최신가
# 추세 강도 = (현재 RS / n일 전 RS - 1) × 100 (%)
import logging
import sqlite3
from datetime import date, timedelta

logger = logging.getLogger(__name__)

from storage.database import DB_PATH


def _get_latest_price(indicator: str, db_path: str = DB_PATH) -> float | None:
    """DB에서 지표의 최신 유효 가격 반환"""
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT value FROM indicators WHERE indicator=? ORDER BY date DESC LIMIT 1",
        (indicator,),
    ).fetchone()
    conn.close()
    return float(row[0]) if row and row[0] is not None else None


def _get_price_n_days_ago(
    indicator: str, n: int = 20, db_path: str = DB_PATH
) -> float | None:
    """n 영업일 전 근사값: 오늘 기준 n+7일 이전 데이터 중 가장 최신 값"""
    cutoff = (date.today() - timedelta(days=n + 7)).isoformat()
    upper  = (date.today() - timedelta(days=n - 3)).isoformat()
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        """
        SELECT value FROM indicators
        WHERE indicator=? AND date BETWEEN ? AND ?
        ORDER BY date DESC LIMIT 1
        """,
        (indicator, cutoff, upper),
    ).fetchone()
    conn.close()
    return float(row[0]) if row and row[0] is not None else None


def compute_relative_strength(
    numerator: str,
    denominator: str,
    db_path: str = DB_PATH,
) -> float | None:
    """
    두 지표의 최신가 비율(상대강도) 반환.
    예: compute_relative_strength("SMH", "SPY") → 2.15 (SMH가 SPY의 2.15배)
    """
    num_price = _get_latest_price(numerator, db_path)
    den_price = _get_latest_price(denominator, db_path)
    if num_price is None or den_price is None or den_price == 0:
        logger.warning(f"[RS] {numerator}/{denominator}: 데이터 없음 (num={num_price}, den={den_price})")
        return None
    rs = round(num_price / den_price, 6)
    logger.info(f"[RS] {numerator}/{denominator}: {num_price:.2f}/{den_price:.2f} = {rs:.4f}")
    return rs


def compute_rs_trend(
    rs_indicator: str,
    lookback_days: int = 20,
    db_path: str = DB_PATH,
) -> float | None:
    """
    RS 지표의 n일 추세 변화율(%) 반환.
    예: SMH/SPY 상대강도가 20일 전보다 얼마나 변했는지
    """
    current = _get_latest_price(rs_indicator, db_path)
    past    = _get_price_n_days_ago(rs_indicator, n=lookback_days, db_path=db_path)
    if current is None or past is None or past == 0:
        return None
    return round((current / past - 1) * 100, 2)


def build_rs_summary(db_path: str = DB_PATH) -> dict:
    """
    RS 지표 전체 요약 딕셔너리 반환
    {
        "RS_SMH_SPY": {"ratio": 2.15, "trend_20d": 3.2, "label": "반도체/S&P500"},
        "RS_XLU_SPY": {"ratio": 0.48, "trend_20d": -1.1, "label": "유틸리티/S&P500"},
    }
    """
    pairs = [
        ("RS_SMH_SPY", "SMH", "SPY", "반도체/S&P500 RS"),
        ("RS_XLU_SPY", "XLU", "SPY", "유틸리티(전력)/S&P500 RS"),
    ]
    result = {}
    for rs_key, num, den, label in pairs:
        ratio = _get_latest_price(rs_key, db_path)
        if ratio is None:
            ratio = compute_relative_strength(num, den, db_path)
        trend = compute_rs_trend(rs_key, lookback_days=20, db_path=db_path)
        result[rs_key] = {
            "label": label,
            "ratio": ratio,
            "trend_20d_pct": trend,
            "numerator":   num,
            "denominator": den,
        }
    return result
