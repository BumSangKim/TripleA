# main.py
# 파이프라인 통합 진입점 - 수집 → 저장 → 요약 → 전송
import logging
from datetime import date

from config import validate_config
from database import init_db, upsert_indicator, log_collect, get_previous_value
from collector import (
    fetch_ecos_keystat,
    fetch_fred,
    fetch_nyfed_pmi_sdt,
    fetch_dxy_yahoo,
    fetch_yahoo_quote,
    fetch_fmp_capex,
    fetch_naver_news,
    fetch_rss,
    fetch_krx_index,
    fetch_kosis,
)
from summarizer import build_summary
from telegram_sender import send_report, send_ir_summaries
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
# 실시간 가격(KOSPI/KOSDAQ/금/원유)은 Yahoo Finance에서 별도 수집
ECOS_KEY_MAP = {
    "소비자물가지수":                        ("CPI",          "index"),
    "생산자물가지수":                        ("PPI",          "index"),
    "원/달러 환율(종가)":                    ("USD_KRW",      "원"),
    "한국은행 기준금리":                     ("BASE_RATE",    "%"),
    "실업률":                                ("UNEMPLOYMENT", "%"),
    "국고채수익률(3년)":                     ("BOND_3Y",      "%"),
    "경제성장률(실질, 계절조정 전기대비)":   ("GDP_GROWTH",   "%"),
    "소비자심리지수":                        ("CSI",          ""),
}

# Yahoo Finance에서 실시간 수집할 지표 (실제 날짜 사용)
YAHOO_QUOTE_MAP = {
    "^KS11":   ("KOSPI",     "pt",      "Yahoo:^KS11"),
    "^KQ11":   ("KOSDAQ",    "pt",      "Yahoo:^KQ11"),
    "GC=F":    ("GOLD",      "USD/oz",  "Yahoo:GC=F"),
    "BZ=F":    ("DUBAI_OIL", "USD/bbl", "Yahoo:BZ=F"),
}


def safe_store(indicator: str, value, source: str, unit: str = "", date_str: str = None):
    """수집값 저장 실패 시 전일값으로 대체. date_str 미지정 시 TODAY_ISO 사용"""
    store_date = date_str or TODAY_ISO
    if value is None:
        fallback = get_previous_value(indicator, db_path=DB_PATH)
        logger.warning(f"[{indicator}] 수집 실패 -> 전일값 대체: {fallback}")
        log_collect(indicator, "fail", "전일값 대체", db_path=DB_PATH)
        value = fallback
    else:
        log_collect(indicator, "success", db_path=DB_PATH)

    if value is not None:
        try:
            upsert_indicator(store_date, indicator, float(value), source, unit, db_path=DB_PATH)
            logger.info(f"  [{indicator}] {float(value):.4f} {unit} ({store_date}) 저장 완료")
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


def _fred_date_val(obs: list) -> tuple[str, float] | None:
    """FRED observations에서 실제 관측 날짜와 값을 함께 반환 (날짜, 값)"""
    if not obs:
        return None
    for item in obs:
        raw = str(item.get("value", "")).strip()
        if raw and raw != ".":
            try:
                return (item["date"], float(raw))
            except (ValueError, KeyError):
                continue
    return None


def collect_all_indicators():
    logger.info("=" * 60)
    logger.info(f"데이터 수집 시작: {TODAY_ISO}")

    # ── 한국은행 ECOS KeyStatisticList (월/분기 지표) ───────────────
    logger.info("[ECOS] KeyStatisticList 수집 중...")
    keystat = fetch_ecos_keystat()
    if keystat:
        logger.info(f"[ECOS] {len(keystat)}개 지표 수신")
        for kor_name, (eng_key, unit) in ECOS_KEY_MAP.items():
            item = keystat.get(kor_name)
            val = item["value"] if item else None
            safe_store(eng_key, val, "ECOS:KeyStatisticList", unit)
    else:
        logger.error("[ECOS] KeyStatisticList 수집 완전 실패")
        for _, (eng_key, unit) in ECOS_KEY_MAP.items():
            safe_store(eng_key, None, "ECOS:fallback", unit)

    # ── Yahoo Finance 실시간 가격 (KOSPI/KOSDAQ/금/두바이유) ─────────
    logger.info("[Yahoo] 실시간 가격 수집 중 (KOSPI/KOSDAQ/GOLD/DUBAI_OIL)...")
    for symbol, (ind_key, unit, source) in YAHOO_QUOTE_MAP.items():
        result = fetch_yahoo_quote(symbol)
        if result:
            actual_date, val = result
            safe_store(ind_key, val, source, unit, date_str=actual_date)
        else:
            # Yahoo 실패 시 ECOS 값으로 대체 (fallback)
            ecos_fallbacks = {
                "KOSPI":     "코스피지수",
                "KOSDAQ":    "코스닥지수",
                "GOLD":      "금",
                "DUBAI_OIL": "Dubai유(현물)",
            }
            fb_name = ecos_fallbacks.get(ind_key)
            fb_val = keystat.get(fb_name, {}).get("value") if keystat and fb_name else None
            safe_store(ind_key, fb_val, f"ECOS:fallback({symbol})", unit)

    # ── FRED 미국 지표 ──────────────────────────────────────────────
    logger.info("[FRED] 미국 경제지표 수집 중...")

    # WTI 국제유가 - Yahoo(최신) vs FRED(공식, 1-2일 지연)
    obs = fetch_fred("DCOILWTICO")
    fred_wti = _fred_date_val(obs)   # (date, value)
    yahoo_wti = fetch_yahoo_quote("CL=F")
    # 더 최신 날짜의 소스 사용
    if yahoo_wti and (fred_wti is None or yahoo_wti[0] >= fred_wti[0]):
        safe_store("WTI", yahoo_wti[1], "Yahoo:CL=F", "USD/bbl", date_str=yahoo_wti[0])
    elif fred_wti:
        safe_store("WTI", fred_wti[1], "FRED:DCOILWTICO", "USD/bbl", date_str=fred_wti[0])
    else:
        safe_store("WTI", None, "FRED:DCOILWTICO", "USD/bbl")

    # 미국 CPI (월별 지표 - 실제 관측 날짜 사용)
    obs = fetch_fred("CPIAUCSL")
    fred_cpi = _fred_date_val(obs)
    if fred_cpi:
        safe_store("US_CPI", fred_cpi[1], "FRED:CPIAUCSL", "index", date_str=fred_cpi[0])
    else:
        safe_store("US_CPI", None, "FRED:CPIAUCSL", "index")

    # 미국 기준금리 (월별 - 실제 관측 날짜 사용)
    obs = fetch_fred("FEDFUNDS")
    fred_fedfunds = _fred_date_val(obs)
    if fred_fedfunds:
        safe_store("FED_RATE", fred_fedfunds[1], "FRED:FEDFUNDS", "%", date_str=fred_fedfunds[0])
    else:
        safe_store("FED_RATE", None, "FRED:FEDFUNDS", "%")

    # 미국 10Y 국채금리 - Yahoo(최신 거래일) vs FRED(공식, 1일 지연)
    obs = fetch_fred("DGS10")
    fred_us10y = _fred_date_val(obs)
    yahoo_us10y = fetch_yahoo_quote("^TNX")
    if yahoo_us10y and (fred_us10y is None or yahoo_us10y[0] >= fred_us10y[0]):
        val = yahoo_us10y[1] / 10 if yahoo_us10y[1] > 10 else yahoo_us10y[1]
        safe_store("US10Y", val, "Yahoo:^TNX", "%", date_str=yahoo_us10y[0])
    elif fred_us10y:
        safe_store("US10Y", fred_us10y[1], "FRED:DGS10", "%", date_str=fred_us10y[0])
    else:
        safe_store("US10Y", None, "FRED:DGS10", "%")

    # 달러 무역가중지수 (FRED:DTWEXBGS, 주별)
    obs = fetch_fred("DTWEXBGS")
    fred_dtwex = _fred_date_val(obs)
    if fred_dtwex:
        safe_store("USD_INDEX", fred_dtwex[1], "FRED:DTWEXBGS", "index", date_str=fred_dtwex[0])
    else:
        safe_store("USD_INDEX", None, "FRED:DTWEXBGS", "index")

    # 실제 DXY (ICE US Dollar Index, Yahoo Finance: DX-Y.NYB)
    dxy_result = fetch_yahoo_quote("DX-Y.NYB")
    if dxy_result:
        safe_store("DXY", dxy_result[1], "YAHOO:DX-Y.NYB", "index", date_str=dxy_result[0])
    else:
        safe_store("DXY", None, "YAHOO:DX-Y.NYB", "index")

    # ── NY Fed 공급망 압력지수 (GSCPI · PMI Supplier Delivery Times 기반) ────
    logger.info("[NY Fed] 공급망 압력지수(GSCPI/PMI 기반) 수집 중...")
    pmi_sdt_val = fetch_nyfed_pmi_sdt()
    if pmi_sdt_val is not None:
        safe_store("PMI_SDT", pmi_sdt_val, "NY_FED:GSCPI", "")
    else:
        logger.info("[NY Fed] GSCPI 수집 실패 - 건너뜀")

    # ── Hyperscaler AI CapEx (Deep Research S1) ─────────────────────────
    logger.info("[FMP] Hyperscaler CapEx 수집 중 (MSFT/GOOGL/META/AMZN)...")
    import time as _time
    for ticker in ["MSFT", "GOOGL", "META", "AMZN"]:
        rows = fetch_fmp_capex(ticker, limit=5)
        for row in rows:
            date_str = row["date"]          # e.g. "2026-03-31"
            capex_b  = row["capex_b"]       # Billion USD (양수)
            ind_key  = f"CAPEX_{ticker}"
            try:
                upsert_indicator(date_str, ind_key, capex_b, f"FMP:{ticker}", "B USD", db_path=DB_PATH)
            except Exception as e:
                logger.error(f"  [{ind_key}@{date_str}] 저장 오류: {e}")
        if rows:
            latest = rows[0]
            logger.info(f"  [CAPEX_{ticker}] 최신: {latest['date']} = ${latest['capex_b']:.2f}B ({len(rows)}분기 저장)")
            log_collect(f"CAPEX_{ticker}", "success", db_path=DB_PATH)
        else:
            log_collect(f"CAPEX_{ticker}", "fail", "FMP 수집 실패", db_path=DB_PATH)
        _time.sleep(0.3)  # FMP rate limit

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

    # ── IR 스크래핑 및 Gemini 요약 ────────────────────────────────
    logger.info("[IR] 신규 8-K 파일링 확인 중 (MSFT/AMZN/META/GOOGL)...")
    try:
        from ir_scraper import get_new_filings, fetch_filing_text
        from gemini_client import summarize_ir
        from database import save_ir_filing

        new_filings = get_new_filings(db_path=DB_PATH)
        if not new_filings:
            logger.info("[IR] 신규 파일링 없음 - IR 요약 건너뜀")
        else:
            logger.info(f"[IR] 신규 파일링 {len(new_filings)}건 발견 - Gemini 요약 시작")
            summarized = []
            for f in new_filings:
                try:
                    text = fetch_filing_text(f["accession"], f["cik"], f["doc"])
                    if not text:
                        logger.warning(f"[IR] 문서 내용 없음: {f['ticker']} {f['date']}")
                        continue
                    summary_text = summarize_ir(f["company"], f["date"], text)
                    save_ir_filing(f, summary_text, db_path=DB_PATH)
                    summarized.append({**f, "summary": summary_text})
                    logger.info(f"[IR] 요약 완료: {f['ticker']} {f['date']}")
                except Exception as e:
                    logger.error(f"[IR] 오류 ({f['ticker']} {f['date']}): {e}")

            send_ir_summaries(summarized)
            logger.info(f"[IR] 텔레그램 전송 완료: {len(summarized)}건")

    except Exception as e:
        logger.error(f"[IR] 전체 플로우 오류: {e}")
