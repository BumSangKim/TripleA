# main.py
# 파이프라인 통합 진입점 - 수집 → 저장 → 요약 → 전송
import logging
from datetime import date

from config import validate_config
from database import init_db, upsert_indicator, log_collect, get_previous_value
from collector import (
    fetch_ecos_keystat,
    fetch_fred,
    fetch_naver_news,
    fetch_rss,
    fetch_krx_index,
    fetch_kosis,
)
from summarizer import build_summary
from telegram_sender import send_report
from monitor import alert_if_fail

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
TODAY_ISO = date.today().isoformat()

# ECOS KeyStatisticList 지표명 -> (내부키, 단위) 매핑
ECOS_KEY_MAP = {
    "소비자물가지수":                        ("CPI",          "%"),
    "생산자물가지수":                        ("PPI",          "%"),
    "원/달러 환율(종가)":                    ("USD_KRW",      "원"),
    "한국은행 기준금리":                     ("BASE_RATE",    "%"),
    "코스피지수":                            ("KOSPI",        "pt"),
    "실업률":                                ("UNEMPLOYMENT", "%"),
    "Dubai유(현물)":                         ("DUBAI_OIL",    "USD/bbl"),
    "금":                                    ("GOLD",         "USD/oz"),
    "국고채수익률(3년)":                     ("BOND_3Y",      "%"),
    "경제성장률(실질, 계절조정 전기대비)":   ("GDP_GROWTH",   "%"),
    "코스닥지수":                            ("KOSDAQ",       "pt"),
    "소비자심리지수":                        ("CSI",          ""),
}


def safe_store(indicator: str, value, source: str, unit: str = ""):
    """수집값 저장 실패 시 전일값으로 대체"""
    if value is None:
        fallback = get_previous_value(indicator, db_path=DB_PATH)
        logger.warning(f"[{indicator}] 수집 실패 -> 전일값 대체: {fallback}")
        log_collect(indicator, "fail", "전일값 대체", db_path=DB_PATH)
        value = fallback
    else:
        log_collect(indicator, "success", db_path=DB_PATH)

    if value is not None:
        try:
            upsert_indicator(TODAY_ISO, indicator, float(value), source, unit, db_path=DB_PATH)
            logger.info(f"  [{indicator}] {float(value):.4f} {unit} 저장 완료")
        except Exception as e:
            logger.error(f"  [{indicator}] 저장 오류: {e}")


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


def collect_all_indicators():
    logger.info("=" * 60)
    logger.info(f"데이터 수집 시작: {TODAY_ISO}")

    # ── 한국은행 ECOS KeyStatisticList ──────────────────────────────
    logger.info("[ECOS] KeyStatisticList 수집 중...")
    keystat = fetch_ecos_keystat()
    if keystat:
        logger.info(f"[ECOS] {len(keystat)}개 지표 수신")
        for kor_name, (eng_key, unit) in ECOS_KEY_MAP.items():
            item = keystat.get(kor_name)
            val = item["value"] if item else None
            safe_store(eng_key, val, f"ECOS:KeyStatisticList", unit)
    else:
        logger.error("[ECOS] KeyStatisticList 수집 완전 실패")
        for _, (eng_key, unit) in ECOS_KEY_MAP.items():
            safe_store(eng_key, None, "ECOS:fallback", unit)

    # ── FRED 미국 지표 ──────────────────────────────────────────────
    logger.info("[FRED] 미국 경제지표 수집 중...")

    # WTI 국제유가
    obs = fetch_fred("DCOILWTICO")
    safe_store("WTI", _fred_val(obs), "FRED:DCOILWTICO", "USD/bbl")

    # 미국 CPI
    obs = fetch_fred("CPIAUCSL")
    safe_store("US_CPI", _fred_val(obs), "FRED:CPIAUCSL", "index")

    # 미국 기준금리
    obs = fetch_fred("FEDFUNDS")
    safe_store("FED_RATE", _fred_val(obs), "FRED:FEDFUNDS", "%")

    # 공급망 압력지수 (단종 가능 - 실패해도 파이프라인 계속)
    obs = fetch_fred("GSCPI")
    val = _fred_val(obs)
    if val is not None:
        safe_store("GSCPI", val, "FRED:GSCPI", "")
    else:
        logger.info("[FRED] GSCPI 없음 (단종되었을 수 있음) - 건너뜀")

    # ── Naver 뉴스 헤드라인 (선택) ──────────────────────────────────
    try:
        news = fetch_naver_news("경제 인플레이션", display=5)
        if news:
            logger.info(f"[NAVER] 뉴스 {len(news)}건 수집")
    except Exception as e:
        logger.warning(f"[NAVER] 수집 건너뜀: {e}")

    logger.info("=" * 60)
    logger.info("전체 수집 완료")


if __name__ == "__main__":
    validate_config()
    init_db(DB_PATH)
    collect_all_indicators()
    summary = build_summary(db_path=DB_PATH)
    send_report(db_path=DB_PATH)
    alert_if_fail(db_path=DB_PATH)
