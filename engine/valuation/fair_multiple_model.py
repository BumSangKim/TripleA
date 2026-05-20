# engine/valuation/fair_multiple_model.py
# 적정 멀티플 추정 모델
#
# 두 단계:
#   1. 데이터 < MIN_SAMPLES → 휴리스틱 모델 (섹터 기준 + 매크로/펀더멘털 조정)
#   2. 데이터 ≥ MIN_SAMPLES → Ridge Regression: ln(EV/EBITDA) = α + β·X
#
# 수식:
#   ln(EV/EBITDA_fair) = α_s + β1·Rate + β2·InflationExcess
#                       + β3·Bottleneck + β4·ROIC + β5·Growth + β6·Margin
#   FairMultiple = exp(predicted)

import logging
import sqlite3
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MIN_SAMPLES = 20  # Ridge 사용 최소 샘플 수

# ── 섹터별 파라미터 표 ────────────────────────────────────────────────────────

# 중립 거시환경(금리 3.5%, 물가 2%, 병목 0σ) 기준 기본 EV/EBITDA
_BASE_EV_EBITDA: dict[str, float] = {
    "tech_growth":   22.0,  # 고성장 테크 (MSFT, GOOGL, META, AMZN)
    "semiconductor": 18.0,  # 반도체 (NVDA, Samsung, SK Hynix)
    "auto":           8.0,  # 자동차 (Hyundai)
    "materials":      9.0,  # 소재 (POSCO)
    "energy":         8.5,  # 에너지
    "financials":    12.0,  # 금융
    "default":       14.0,
}

# PER 역산 가이드: fair_per ≈ fair_ev_ebitda × per_ratio_factor
_PER_RATIO: dict[str, float] = {
    "tech_growth":   1.6,
    "semiconductor": 1.5,
    "auto":          1.1,
    "materials":     1.1,
    "default":       1.3,
}

# PBR 가이드: fair_pbr ≈ roe / required_return (Gordon–ROE)
_REQUIRED_RETURN: dict[str, float] = {
    "tech_growth":   0.10,
    "semiconductor": 0.12,
    "auto":          0.09,
    "materials":     0.09,
    "default":       0.10,
}

# 금리 민감도: 금리 1% 상승 시 EV/EBITDA 변화 (x배)
# 성장주는 할인율 상승에 매우 취약
_RATE_SENSITIVITY: dict[str, float] = {
    "tech_growth":   -2.5,
    "semiconductor": -1.8,
    "auto":          -0.8,
    "materials":     -0.6,
    "energy":        -0.3,   # 금리 상승 = 인플레 연동 → 상대적 방어
    "financials":    +0.5,   # 은행은 금리 프리미엄 수혜
    "default":       -1.5,
}

# 병목 민감도: 병목 1σ 상승 시 EV/EBITDA 변화
# (+) 가격결정력 우위 (공급 부족 → 판가 ↑), (-) 비용 압박형
_BOTTLENECK_SENSITIVITY: dict[str, float] = {
    "tech_growth":   -0.8,   # 주로 소프트웨어 비용 상승
    "semiconductor": +0.6,   # 공급 부족 시 ASP ↑ 수혜
    "auto":          -1.2,   # 부품 공급망 병목에 치명적
    "materials":     +0.7,   # 원자재 생산자 — 가격 결정력
    "energy":        +0.5,   # 에너지 공급 타이트 = 유가 ↑
    "financials":    -0.3,
    "default":       -0.4,
}


class FairMultipleModel:
    """
    섹터별 적정 EV/EBITDA 추정 모델.

    사용법
    ------
    model = FairMultipleModel(sector="semiconductor")
    model.fit(df)  # 데이터가 충분하면 Ridge 학습, 아니면 heuristic
    fair_ev, model_type = model.predict(rate=4.5, inflation=3.2, bottleneck=0.8,
                                         roic=25.0, revenue_growth=15.0, ebitda_margin=35.0)
    """

    def __init__(self, sector: str = "default"):
        self.sector = sector
        self._ridge = None
        self._scaler_mean: Optional[pd.Series] = None
        self._scaler_std: Optional[pd.Series] = None
        self._feature_cols = [
            "rate", "inflation_excess", "bottleneck",
            "roic", "revenue_growth", "ebitda_margin",
        ]

    # ── 휴리스틱 모델 ─────────────────────────────────────────────────

    def _heuristic_ev_ebitda(
        self,
        rate: float,
        inflation: float,
        bottleneck: float,
        roic: float = 15.0,
        revenue_growth: float = 5.0,
        ebitda_margin: float = 20.0,
    ) -> float:
        """
        공식 기반 적정 EV/EBITDA 추정.

        base + macro_adjustment + fundamental_adjustment
        """
        s = self.sector
        base = _BASE_EV_EBITDA.get(s, _BASE_EV_EBITDA["default"])

        # ── 매크로 조정 ──────────────────────────────────────────────
        # 금리: 기준금리 3.5% 초과분에 비례 페널티
        rate_sens = _RATE_SENSITIVITY.get(s, -1.5)
        rate_adj = rate_sens * max(0.0, rate - 3.5)

        # 물가: 2% 목표 초과분 페널티
        inf_excess = max(0.0, inflation - 2.0)
        inflation_adj = -0.35 * inf_excess

        # 병목
        bn_sens = _BOTTLENECK_SENSITIVITY.get(s, -0.4)
        bottleneck_adj = bn_sens * bottleneck

        # ── 펀더멘털 조정 ────────────────────────────────────────────
        # ROIC: 15% 기준점 대비 초과 수익성 프리미엄
        roic_adj = 0.15 * (roic - 15.0)
        # 매출성장률: 양수 성장 프리미엄
        growth_adj = 0.08 * max(revenue_growth, 0.0)
        # EBITDA 마진: 20% 기준점 대비 마진 품질
        margin_adj = 0.06 * (ebitda_margin - 20.0)

        fair = base + rate_adj + inflation_adj + bottleneck_adj + roic_adj + growth_adj + margin_adj
        return max(fair, 3.0)  # Floor: 최소 3배

    def _heuristic_per(
        self,
        fair_ev_ebitda: float,
        rate: float,
        roic: float = 15.0,
    ) -> float:
        """EV/EBITDA 기반 fair PER 추정 (섹터별 계수 적용)"""
        per_factor = _PER_RATIO.get(self.sector, _PER_RATIO["default"])
        # 금리가 높을수록 PER multiplier 감소
        rate_discount = 1.0 - 0.04 * max(0, rate - 3.5)
        return max(fair_ev_ebitda * per_factor * rate_discount, 5.0)

    def _heuristic_pbr(
        self,
        roe: float,
        rate: float,
    ) -> float:
        """
        Gordon-ROE PBR 모델:
          PBR = ROE / required_return
          required_return = risk_free + risk_premium ≈ rate + 4%
        """
        required_return = max(rate / 100 + 0.04, 0.06)  # minimum 6%
        roe_frac = max(roe, 0.0) / 100.0
        return max(roe_frac / required_return, 0.5)

    # ── Ridge Regression Model ────────────────────────────────────────

    def fit(self, df: pd.DataFrame) -> bool:
        """
        Ridge 회귀 학습.

        df 컬럼: rate, inflation_excess, bottleneck, roic,
                 revenue_growth, ebitda_margin, ev_ebitda (target)

        Returns True if fitted successfully.
        """
        try:
            from sklearn.linear_model import Ridge
        except ImportError:
            logger.warning("[FairModel] scikit-learn 없음 — heuristic 모드만 사용")
            return False

        cols = [c for c in self._feature_cols if c in df.columns] + ["ev_ebitda"]
        sub = df[cols].copy()
        sub = sub[sub["ev_ebitda"] > 0].dropna()

        if len(sub) < MIN_SAMPLES:
            logger.info("[FairModel/%s] 샘플 부족 (%d < %d) — heuristic 사용",
                        self.sector, len(sub), MIN_SAMPLES)
            return False

        X = sub[[c for c in self._feature_cols if c in sub.columns]]
        y = np.log(sub["ev_ebitda"])

        self._scaler_mean = X.mean()
        self._scaler_std = X.std().replace(0, 1.0)
        X_scaled = (X - self._scaler_mean) / self._scaler_std

        self._ridge = Ridge(alpha=1.0)
        self._ridge.fit(X_scaled.values, y.values)
        self._feature_cols = list(X.columns)

        logger.info("[FairModel/%s] Ridge 학습 완료 (n=%d, features=%s)",
                    self.sector, len(sub), self._feature_cols)
        return True

    def _predict_ridge(
        self,
        rate: float,
        inflation: float,
        bottleneck: float,
        roic: float,
        revenue_growth: float,
        ebitda_margin: float,
    ) -> Optional[float]:
        if self._ridge is None or self._scaler_mean is None:
            return None
        try:
            raw = {
                "rate": rate,
                "inflation_excess": max(0.0, inflation - 2.0),
                "bottleneck": bottleneck,
                "roic": roic,
                "revenue_growth": revenue_growth,
                "ebitda_margin": ebitda_margin,
            }
            x = pd.Series({f: raw.get(f, 0.0) for f in self._feature_cols})
            x_scaled = (x - self._scaler_mean) / self._scaler_std
            log_pred = self._ridge.predict([x_scaled.values])[0]
            return float(np.exp(log_pred))
        except Exception as e:
            logger.warning("[FairModel] Ridge 예측 실패: %s", e)
            return None

    # ── 통합 예측 API ─────────────────────────────────────────────────

    def predict(
        self,
        rate: float,
        inflation: float,
        bottleneck: float,
        roic: float = 15.0,
        revenue_growth: float = 5.0,
        ebitda_margin: float = 20.0,
        roe: float = 15.0,
    ) -> dict:
        """
        적정 멀티플 예측.

        Returns
        -------
        dict with keys:
            fair_ev_ebitda, fair_per, fair_pbr, model_type
        """
        # Ridge 시도 → 실패 시 heuristic 폴백
        ridge_ev = self._predict_ridge(rate, inflation, bottleneck, roic, revenue_growth, ebitda_margin)
        if ridge_ev is not None:
            model_type = "ridge"
            fair_ev = ridge_ev
        else:
            model_type = "heuristic"
            fair_ev = self._heuristic_ev_ebitda(
                rate, inflation, bottleneck, roic, revenue_growth, ebitda_margin
            )

        fair_per = self._heuristic_per(fair_ev, rate, roic)
        fair_pbr = self._heuristic_pbr(roe, rate)

        return {
            "fair_ev_ebitda": round(fair_ev, 2),
            "fair_per": round(fair_per, 2),
            "fair_pbr": round(fair_pbr, 2),
            "model_type": model_type,
        }


# ── 섹터별 모델 일괄 학습 ─────────────────────────────────────────────────────

def fit_sector_models(db_path: str) -> dict[str, FairMultipleModel]:
    """
    DB의 valuation_results + company_fundamentals + indicators 데이터를 합쳐
    섹터별 Ridge 회귀를 학습한다.
    데이터가 부족한 섹터는 heuristic 모드로 유지.
    """
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(
            """
            SELECT
                v.date, v.ticker, v.sector,
                v.current_ev_ebitda as ev_ebitda,
                f.roic, f.revenue_growth_yoy as revenue_growth, f.ebitda_margin
            FROM valuation_results v
            LEFT JOIN company_fundamentals f
                ON v.ticker=f.ticker
            WHERE v.current_ev_ebitda > 0
            ORDER BY v.date
            """,
            conn,
        )

        # 매크로 데이터 (indicators 테이블)
        macro = {}
        for ind in ["US10Y", "US_CPI"]:
            sub = pd.read_sql_query(
                "SELECT date, value FROM indicators WHERE indicator=? AND is_stale=0 ORDER BY date",
                conn, params=(ind,),
            )
            if not sub.empty:
                sub["date"] = pd.to_datetime(sub["date"]).dt.date.astype(str)
                macro[ind] = sub.set_index("date")["value"]
    except Exception as e:
        logger.warning("[FairModel] 학습 데이터 로드 실패: %s", e)
        return {}
    finally:
        conn.close()

    if df.empty:
        return {}

    df["date"] = pd.to_datetime(df["date"]).dt.date.astype(str)

    # 매크로 컬럼 merge
    if "US10Y" in macro:
        df["rate"] = df["date"].map(macro["US10Y"])
    if "US_CPI" in macro:
        cpi = macro["US_CPI"]
        cpi_yoy = cpi.pct_change(12) * 100  # YoY%
        df["inflation"] = df["date"].map(cpi_yoy)
        df["inflation_excess"] = (df["inflation"] - 2.0).clip(lower=0)

    df = df.dropna(subset=["ev_ebitda", "roic"])

    models: dict[str, FairMultipleModel] = {}
    for sector in df["sector"].dropna().unique():
        sub = df[df["sector"] == sector].copy()
        m = FairMultipleModel(sector=str(sector))
        m.fit(sub)
        models[str(sector)] = m
        logger.info("[FairModel] 섹터 '%s' 모델 준비 완료 (n=%d)", sector, len(sub))

    return models
