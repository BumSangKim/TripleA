# main.py
# 파이프라인 통합 진입점 - 수집 → 저장 → 요약 → 전송
import logging
import os
from datetime import date

from config import validate_config
from database import init_db, upsert_indicator, log_collect, get_previous_value
from collector import (
    fetch_ecos,
    fetch_kosis,
    fetch_krx_index,
    fetch_fred,
    fetch_naver_news,
    fetch_rss,
)
from summarizer import build_summary
from telegram_sender import send_report
from monitor import alert_if_fail

# 로그 설정
logging.basicConfig(
    handlers=[
        logging.FileHandler("pipeline.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

DB_PATH = "economic_data.db"
TODAY = date.today().strftime("%Y%m%d")
TODAY_ISO = date.today().isoformat()


def safe_store(indicator: str, value, source: str, unit: str = ""):
    """수집값 저장 실패 시 전일값으로 대체"""
    if value is None:
        fallback = get_previous_value(indicator, db_path=DB_PATH)
        logger.warning(f"[{indicator}] 수집 실패 → 전일값 대체: {fallback}")
        log_collect(indicator, "fail", "전일값 대체", db_path=DB_PATH)
        value = fallback
    else:
        log_collect(indicator, "success", db_path=DB_PATH)

    if value is not None:
        upsert_indicator(TODAY_ISO, indicator, float(value), source, unit, db_path=DB_PATH)


def collect_all_indicators():
    logger.info("=" * 50)
    logger.info("데이터 수집 시작")

    # ── 한국은행 ECOS ─────────────────────────────
    # CPI (소비자물가지수)
    rows = fetch_ecos("901Y009", "MM", "202301", TODAY[:6])
    val = _ecos_val(rows)
    safe_store("CPI", val, "ECOS:901Y009", "%")

    # 생산자물가지수 (PPI)
    rows = fetch_ecos("403Y014", "MM", "202301", TODAY[:6])
    val = _ecos_val(rows)
    safe_store("PPI", val, "ECOS:403Y014", "%")

    # 원/달러 환율
    rows = fetch_ecos("731Y001", "DD", "20240101", TODAY)
    val = _ecos_val(rows)
    safe_store("USD_KRW", val, "ECOS:731Y001", "원")

    # 기준금리
    rows = fetch_ecos("722Y001", "MM", "202301", TODAY[:6])
    val = _ecos_val(rows)
    safe_store("BASE_RATE", val, "ECOS:722Y001", "%")

    # 두바이유
    rows = fetch_ecos("902Y014", "DD", "20240101", TODAY)
    val = _ecos_val(rows)
    safe_store("DUBAI_OIL", val, "ECOS:902Y014", "USD/bbl")

    # ── KRX ──────────────────────────────────────
    krx = fetch_krx_index("KOSPI")
    val = _krx_val(krx)
    safe_store("KOSPI", val, "KRX", "pt")

    # ── FRED ─────────────────────────────────────
    # WTI 국제유가
    obs = fetch_fred("DCOILWTICO")
    val = _fred_val(obs)
    safe_store("WTI", val, "FRED:DCOILWTICO", "USD/bbl")

    # 금 가격
    obs = fetch_fred("GOLDPMGBD228NLBM")
    val = _fred_val(obs)
    safe_store("GOLD", val, "FRED:GOLDPMGBD228NLBM", "USD/oz")

    # 미국 CPI
    obs = fetch_fred("CPIAUCSL")
    val = _fred_val(obs)
    safe_store("US_CPI", val, "FRED:CPIAUCSL", "%")

    # 미국 기준금리 (Fed Funds Rate)
    obs = fetch_fred("FEDFUNDS")
    val = _fred_val(obs)
    safe_store("FED_RATE", val, "FRED:FEDFUNDS", "%")

    # 공급망 압력지수 (GSCPI)
    obs = fetch_fred("GSCPI")
    val = _fred_val(obs)
    safe_store("GSCPI", val, "FRED:GSCPI", "")

    # ── KOSIS ────────────────────────────────────
    # 실업률
    rows = fetch_kosis("J002", "202301")
    val = _kosis_val(rows)
    safe_store("UNEMPLOYMENT", val, "KOSIS:J002", "%")

    logger.info("데이터 수집 완료")


# ─── 파싱 헬퍼 ───────────────────────────────────

def _ecos_val(rows: list):
    """ECOS rows에서 유효한 최신값 추출"""
    if not rows:
        return None
    # 역순 순회하여 유효한 값 반환
    for row in reversed(rows):
        raw = str(row.get("DATA_VALUE", "")).strip()
        if raw and raw not in ("", ".", "nan"):
            try:
                return float(raw)
            except ValueError:
                continue
    return None


def _fred_val(obs: list):
    """FRED observations에서 유효한 최신값 추출"""
    if not obs:
        return None
    for item in obs:
        raw = str(item.get("value", "")).strip()
        if raw and raw != ".":
            try:
                return float(raw)
            except ValueError:
                continue
    return None


def _krx_val(krx: dict):
    """KRX 응답에서 코스피 종가 추출"""
    if not krx:
        return None
    # KRX 실제 응답 구조에 맞게 파싱
    for key in ("output", "OutBlock_1", "block1"):
        data = krx.get(key)
        if isinstance(data, list) and data:
            for col in ("CLSPRC", "IDX_NM", "OPNPRC"):
                raw = str(data[0].get(col, "")).replace(",", "").strip()
                if raw:
                    try:
                        return float(raw)
                    except ValueError:
                        continue
    return None


def _kosis_val(rows):
    """KOSIS 응답에서 최신 수치 추출"""
    if not isinstance(rows, list) or not rows:
        return None
    for row in reversed(rows):
        raw = str(row.get("DT", row.get("PRD_DE", ""))).strip()
        if raw:
            try:
                return float(raw)
            except ValueError:
                continue
    return None


if __name__ == "__main__":
    validate_config()
    init_db(DB_PATH)
    collect_all_indicators()
    summary = build_summary(db_path=DB_PATH)
    send_report(db_path=DB_PATH)
    alert_if_fail(db_path=DB_PATH)
