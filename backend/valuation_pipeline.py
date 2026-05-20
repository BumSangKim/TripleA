# backend/valuation_pipeline.py
# 밸류에이션 자동화 파이프라인
#
# 실행 흐름:
#   1. 시장 멀티플 + 분기 펀더멘털 수집
#   2. 병목지수 계산 및 DB 저장
#   3. 섹터별 Ridge/Heuristic 적정 멀티플 추정
#   4. 종목별 고평가/저평가 스코어 계산 후 DB 저장
#   5. 결과 반환 (텔레그램 리포트용)

import logging
import sqlite3
from datetime import date
from typing import Any

from storage.database import (
    DB_PATH,
    get_latest_fundamentals,
    get_latest_valuation_results,
    upsert_valuation_result,
)
from ingestion.valuation_collector import TICKER_META, collect_all_valuation_data
from engine.valuation.bottleneck_index import compute_bottleneck_index
from engine.valuation.fair_multiple_model import FairMultipleModel, fit_sector_models
from engine.valuation.mispricing import (
    compute_mispricing,
    compute_overvaluation_score,
    classify_signal,
    compute_zscore_vs_history,
    compute_final_score,
)

logger = logging.getLogger(__name__)


# ── 매크로 스냅샷 조회 ────────────────────────────────────────────────────────

def _get_macro_snapshot(db_path: str) -> dict[str, float]:
    """indicators 테이블에서 현재 매크로 지표 조회"""
    conn = sqlite3.connect(db_path)
    result = {}
    for ind in ["US10Y", "US_CPI", "FED_RATE", "USD_KRW"]:
        row = conn.execute(
            "SELECT value FROM indicators WHERE indicator=? ORDER BY date DESC LIMIT 1",
            (ind,),
        ).fetchone()
        if row:
            result[ind] = float(row[0])
    conn.close()
    return result


def _get_current_multiples(ticker: str, db_path: str) -> dict[str, Any]:
    """company_multiples 테이블에서 최신 멀티플 조회"""
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT ev_ebitda, pe_ratio, pb_ratio, date, sector "
        "FROM company_multiples WHERE ticker=? ORDER BY date DESC LIMIT 1",
        (ticker,),
    ).fetchone()
    conn.close()
    if row is None:
        return {}
    return {
        "ev_ebitda": row[0],
        "pe_ratio":  row[1],
        "pb_ratio":  row[2],
        "date":      row[3],
        "sector":    row[4],
    }


# ── 핵심 파이프라인 ────────────────────────────────────────────────────────────

def run_valuation_pipeline(
    db_path: str = DB_PATH,
    skip_collection: bool = False,
) -> list[dict]:
    """
    밸류에이션 파이프라인 전체 실행.

    Parameters
    ----------
    skip_collection : True면 데이터 수집 단계 건너뜀 (이미 최신 데이터가 있을 때)

    Returns
    -------
    list[dict]
        각 종목의 밸류에이션 결과 리스트 (overvaluation_score 내림차순 정렬)
    """
    today = date.today().isoformat()
    logger.info("[Valuation] 파이프라인 시작 — %s", today)

    # ── Step 1: 데이터 수집 ──────────────────────────────────────────
    if not skip_collection:
        logger.info("[Valuation] Step 1: 시장 멀티플 + 분기 펀더멘털 수집 중...")
        n_ok = collect_all_valuation_data(db_path=db_path)
        logger.info("[Valuation] Step 1 완료: %d 종목 수집", n_ok)
    else:
        logger.info("[Valuation] Step 1: 수집 건너뜀 (skip_collection=True)")

    # ── Step 2: 병목지수 계산 ─────────────────────────────────────────
    logger.info("[Valuation] Step 2: 병목지수 계산 중...")
    bottleneck, bn_components = compute_bottleneck_index(db_path=db_path)
    logger.info("[Valuation] 병목지수 = %.3fσ", bottleneck)

    # ── Step 3: 매크로 스냅샷 ─────────────────────────────────────────
    macro = _get_macro_snapshot(db_path)
    rate = macro.get("US10Y", 4.5)       # US 10년물 금리 (%)
    cpi = macro.get("US_CPI", 310.0)     # 미국 CPI level
    # CPI level → 대략적인 YoY% 추정 (정밀하지 않음, 실제 YoY는 수집 단계에서)
    # 간단히 US_CPI 기반으로 3.0% 가정 (보수적)
    inflation_fallback = 3.0

    logger.info("[Valuation] 매크로: US10Y=%.2f%%, CPI≈%.1f", rate, inflation_fallback)

    # ── Step 4: 섹터별 Ridge 모델 (학습 데이터 있으면) ─────────────────
    logger.info("[Valuation] Step 4: 섹터별 적정 멀티플 모델 준비 중...")
    sector_models = fit_sector_models(db_path=db_path)

    # ── Step 5: 종목별 밸류에이션 계산 ────────────────────────────────
    logger.info("[Valuation] Step 5: 종목별 적정 멀티플 추정 및 괴리율 계산 중...")
    results = []

    for ticker, meta in TICKER_META.items():
        sector = meta["sector"]
        try:
            # 현재 시장 멀티플
            mults = _get_current_multiples(ticker, db_path)
            if not mults:
                logger.debug("[Valuation] %s 멀티플 데이터 없음 — 건너뜀", ticker)
                continue

            current_ev = mults.get("ev_ebitda")
            current_pe = mults.get("pe_ratio")
            current_pb = mults.get("pb_ratio")

            # 기업 펀더멘털 (최신 분기)
            fund = get_latest_fundamentals(ticker, db_path=db_path)
            roic = fund.get("roic") or 15.0
            revenue_growth = fund.get("revenue_growth_yoy") or 5.0
            ebitda_margin = fund.get("ebitda_margin") or 20.0
            roe = fund.get("roe") or roic * 0.8  # ROE ≈ ROIC × (1 + D/E × 0.8) 근사

            # 섹터 모델 선택 (학습된 것 있으면 사용, 없으면 heuristic)
            model = sector_models.get(sector) or FairMultipleModel(sector=sector)

            # 적정 멀티플 예측
            fair = model.predict(
                rate=rate,
                inflation=inflation_fallback,
                bottleneck=bottleneck,
                roic=roic,
                revenue_growth=revenue_growth,
                ebitda_margin=ebitda_margin,
                roe=roe,
            )
            fair_ev = fair["fair_ev_ebitda"]
            fair_pe = fair["fair_per"]
            fair_pb = fair["fair_pbr"]
            model_type = fair["model_type"]

            # 괴리율
            mp_ev = compute_mispricing(current_ev, fair_ev)
            mp_pe = compute_mispricing(current_pe, fair_pe)
            mp_pb = compute_mispricing(current_pb, fair_pb)

            # Z-score vs 자기 과거
            zscore = compute_zscore_vs_history(ticker, current_ev or 0, db_path=db_path)

            # 복합 고평가 스코어
            ov_score = compute_overvaluation_score(mp_ev, mp_pe, mp_pb)

            # 최종 스코어 (미시+거시 combined)
            final_score = compute_final_score(ov_score, zscore)

            # 판단 라벨 (최종 스코어 기준)
            signal = classify_signal(final_score if final_score is not None else ov_score)

            # DB 저장
            upsert_valuation_result(
                date_str=mults.get("date", today),
                ticker=ticker,
                sector=sector,
                current_ev_ebitda=current_ev,
                fair_ev_ebitda=fair_ev,
                mispricing_ev_ebitda=mp_ev,
                current_per=current_pe,
                fair_per=fair_pe,
                mispricing_per=mp_pe,
                current_pbr=current_pb,
                fair_pbr=fair_pb,
                mispricing_pbr=mp_pb,
                overvaluation_score=final_score if final_score is not None else ov_score,
                valuation_signal=signal,
                model_type=model_type,
                bottleneck_used=bottleneck,
                db_path=db_path,
            )

            result_entry = {
                "ticker":              ticker,
                "name":                meta["name"],
                "sector":              sector,
                "current_ev_ebitda":   current_ev,
                "fair_ev_ebitda":      fair_ev,
                "mispricing_ev_ebitda": mp_ev,
                "current_per":         current_pe,
                "fair_per":            fair_pe,
                "overvaluation_score": final_score if final_score is not None else ov_score,
                "valuation_signal":    signal,
                "model_type":          model_type,
                "roic":                roic,
                "revenue_growth":      revenue_growth,
                "ebitda_margin":       ebitda_margin,
            }
            results.append(result_entry)
            logger.info(
                "[Valuation] %s (%s): EV/EBITDA %.1fx → 적정 %.1fx (괴리 %+.1f%%) → %s [%s]",
                ticker, sector,
                current_ev or 0, fair_ev,
                (mp_ev or 0) * 100,
                signal, model_type,
            )

        except Exception as e:
            logger.error("[Valuation] %s 계산 오류: %s", ticker, e)

    # 고평가 순 정렬
    results.sort(key=lambda x: x.get("overvaluation_score") or 0, reverse=True)
    logger.info("[Valuation] 파이프라인 완료: %d종목 처리", len(results))
    return results
