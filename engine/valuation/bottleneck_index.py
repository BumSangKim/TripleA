# engine/valuation/bottleneck_index.py
# 병목지수(Bottleneck Index) 계산
#
# 수식:
#   Bottleneck_t = 0.40·Z(PMI_SDT) + 0.30·Z(WTI) + 0.20·Z(US10Y) + 0.10·Z(CPI_YoY)
#
# 여기서 Z(X) = (X - rolling_mean_24m) / rolling_std_24m
# PMI_SDT(GSCPI)는 이미 σ 단위이므로 직접 사용.
# 양수 → 공급망 압박 / 원자재 비용 ↑ / 금리 부담 ↑

import logging
import sqlite3
from datetime import date

import numpy as np
import pandas as pd

from storage.database import DB_PATH, save_bottleneck_score

logger = logging.getLogger(__name__)

_INDICATOR_WEIGHTS = {
    "PMI_SDT":  0.40,   # NY Fed GSCPI — 공급망 압력 (이미 σ 단위)
    "WTI":      0.30,   # WTI 원유 — 원자재 비용 압력
    "US10Y":    0.20,   # 미국 10년물 금리 — 자본비용 부담
    "US_CPI":   0.10,   # 미국 CPI — 물가 압력
}

_ROLLING_WINDOW = 24  # months (근사치: 주간 데이터면 104주)


def _load_series(indicator: str, n: int, db_path: str) -> pd.Series:
    """indicators 테이블에서 지표 시계열 로드"""
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        "SELECT date, value FROM indicators WHERE indicator=? AND is_stale=0 ORDER BY date ASC LIMIT ?",
        conn, params=(indicator, n),
    )
    conn.close()
    if df.empty:
        return pd.Series(dtype=float)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")["value"].dropna()


def _rolling_zscore(series: pd.Series, window: int = _ROLLING_WINDOW) -> pd.Series:
    """24개월 롤링 Z-score 계산"""
    roll_mean = series.rolling(window=window, min_periods=round(window * 0.5)).mean()
    roll_std = series.rolling(window=window, min_periods=round(window * 0.5)).std()
    roll_std = roll_std.replace(0, np.nan)
    return (series - roll_mean) / roll_std


def compute_bottleneck_history(n_obs: int = 104, db_path: str = DB_PATH) -> pd.DataFrame:
    """
    병목지수 전체 시계열 계산 (최근 n_obs 관측치 기준).

    Returns
    -------
    pd.DataFrame
        columns: date, z_pmi_sdt, z_wti, z_us10y, z_inflation, bottleneck_index
    """
    series_map: dict[str, pd.Series] = {}
    for indicator in _INDICATOR_WEIGHTS:
        s = _load_series(indicator, n_obs + _ROLLING_WINDOW, db_path)
        if s.empty:
            logger.warning("[Bottleneck] %s 데이터 없음 — 0으로 대체", indicator)
            series_map[indicator] = pd.Series(dtype=float)
        else:
            series_map[indicator] = s

    # ── Z-score 계산 ────────────────────────────────────────────────
    # PMI_SDT(GSCPI)는 이미 σ 단위이므로 직접 사용
    pmi_raw = series_map.get("PMI_SDT", pd.Series(dtype=float))
    z_pmi = pmi_raw  # 직접 σ 단위

    wti_raw = series_map.get("WTI", pd.Series(dtype=float))
    z_wti = _rolling_zscore(wti_raw) if not wti_raw.empty else pd.Series(dtype=float)

    us10y_raw = series_map.get("US10Y", pd.Series(dtype=float))
    z_us10y = _rolling_zscore(us10y_raw) if not us10y_raw.empty else pd.Series(dtype=float)

    # US_CPI: YoY 변화율 계산 후 z-score
    cpi_raw = series_map.get("US_CPI", pd.Series(dtype=float))
    if not cpi_raw.empty:
        # YoY 근사: 최근값 대비 12개월 전 변화율 (데이터 주기가 월간이므로 12 lag)
        cpi_yoy = cpi_raw.pct_change(12) * 100
        z_inflation = _rolling_zscore(cpi_yoy)
    else:
        z_inflation = pd.Series(dtype=float)

    # ── 합성 지수 ────────────────────────────────────────────────────
    # 공통 인덱스 (날짜 alignment)
    frames = {}
    if not z_pmi.empty:
        frames["z_pmi_sdt"] = z_pmi
    if not z_wti.empty:
        frames["z_wti"] = z_wti
    if not z_us10y.empty:
        frames["z_us10y"] = z_us10y
    if not z_inflation.empty:
        frames["z_inflation"] = z_inflation

    if not frames:
        logger.warning("[Bottleneck] 모든 지표 데이터 없음 — 병목지수 계산 불가")
        return pd.DataFrame()

    df = pd.DataFrame(frames).ffill().dropna(how="all")

    weights = {
        "z_pmi_sdt": 0.40,
        "z_wti": 0.30,
        "z_us10y": 0.20,
        "z_inflation": 0.10,
    }
    df["bottleneck_index"] = sum(
        df[col].fillna(0) * w
        for col, w in weights.items()
        if col in df.columns
    )
    df = df.reset_index().rename(columns={"index": "date"})
    if "date" not in df.columns:
        df = df.reset_index(drop=False)
        df.rename(columns={df.columns[0]: "date"}, inplace=True)

    df["date"] = pd.to_datetime(df["date"]).dt.date.astype(str)
    return df.tail(n_obs).reset_index(drop=True)


def compute_bottleneck_index(db_path: str = DB_PATH) -> tuple[float, dict]:
    """
    최신 병목지수 스칼라 값 반환 및 DB 저장.

    Returns
    -------
    (float, dict)
        병목지수 값, 컴포넌트별 z-score dict
    """
    df = compute_bottleneck_history(n_obs=104, db_path=db_path)
    if df.empty:
        logger.warning("[Bottleneck] 병목지수 계산 결과 없음 (0.0 반환)")
        return 0.0, {}

    # DataFrame에 date 열이 있는 경우와 index인 경우 모두 처리
    if "date" in df.columns:
        last = df.iloc[-1]
    else:
        last = df.reset_index().iloc[-1]

    bi = float(last.get("bottleneck_index", 0.0))
    components = {
        "z_pmi_sdt": float(last.get("z_pmi_sdt", 0.0)) if "z_pmi_sdt" in last.index else None,
        "z_wti": float(last.get("z_wti", 0.0)) if "z_wti" in last.index else None,
        "z_us10y": float(last.get("z_us10y", 0.0)) if "z_us10y" in last.index else None,
        "z_inflation": float(last.get("z_inflation", 0.0)) if "z_inflation" in last.index else None,
    }
    date_str = str(last.get("date", date.today().isoformat()))

    # DB 저장
    try:
        save_bottleneck_score(
            date_str=date_str,
            bottleneck_index=bi,
            z_pmi_sdt=components.get("z_pmi_sdt"),
            z_wti=components.get("z_wti"),
            z_us10y=components.get("z_us10y"),
            z_inflation=components.get("z_inflation"),
            db_path=db_path,
        )
    except Exception as e:
        logger.error("[Bottleneck] DB 저장 실패: %s", e)

    logger.info("[Bottleneck] %.3fσ (PMI_SDT=%.2f, WTI=%.2f, US10Y=%.2f, CPI=%.2f)",
                bi,
                components.get("z_pmi_sdt") or 0,
                components.get("z_wti") or 0,
                components.get("z_us10y") or 0,
                components.get("z_inflation") or 0)
    return bi, components
