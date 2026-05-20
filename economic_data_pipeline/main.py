# main.py
# 파이프라인 통합 진입점 - 수집 → 저장 → 요약 → 전송
import logging
import time
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

import yaml
from config import validate_config
from database import init_db, upsert_indicator, log_collect, get_previous_value, log_collector_run
from collector import (
    fetch_ecos_keystat,
    fetch_fred,
    fetch_nyfed_pmi_sdt,
    fetch_dxy_yahoo,
    fetch_yahoo_quote,
    fetch_fmp_capex,
    fetch_ercot_grid_status,
    fetch_pjm_load,
    fetch_naver_news,
    fetch_rss,
    fetch_krx_index,
    fetch_kosis,
    get_api_errors,
    clear_api_errors,
)
from summarizer import build_summary
from telegram_sender import send_report, send_ir_summaries, send_api_alert, send_signal_alerts
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
INDICATORS_YAML = Path(__file__).parent / "config" / "indicators.yaml"


def load_indicator_meta() -> dict:
    """indicators.yaml을 단일 지표 메타데이터 출처로 사용한다."""
    try:
        with open(INDICATORS_YAML, encoding="utf-8") as f:
            return yaml.safe_load(f).get("indicators", {})
    except Exception as e:
        logger.error(f"indicators.yaml 로드 실패: {e}")
        return {}


def indicators_by_source(source_type: str, meta: dict = None) -> dict:
    meta = meta or load_indicator_meta()
    return {
        key: value
        for key, value in meta.items()
        if value.get("source_type") == source_type
    }


@contextmanager
def collector_run(collector: str):
    """source별 실행 시작/종료/성공/실패/소요시간 기록."""
    started = datetime.now()
    counts = {"ok": 0, "fail": 0}
    error_msg = None

    def record(success: bool = True, count: int = 1):
        counts["ok" if success else "fail"] += count

    try:
        yield record
    except Exception as e:
        counts["fail"] += 1
        error_msg = str(e)
        logger.exception("[%s] collector block failed", collector)
    finally:
        finished = datetime.now()
        duration_ms = int((finished - started).total_seconds() * 1000)
        if error_msg or (counts["fail"] and not counts["ok"]):
            status = "fail"
        elif counts["fail"]:
            status = "partial"
        else:
            status = "success"
        log_collector_run(
            collector,
            status,
            items_ok=counts["ok"],
            items_fail=counts["fail"],
            duration_ms=duration_ms,
            started_at=started.isoformat(timespec="seconds"),
            finished_at=finished.isoformat(timespec="seconds"),
            error_msg=error_msg,
            db_path=DB_PATH,
        )


def safe_store(
    indicator: str,
    value,
    source: str,
    unit: str = "",
    date_str: str = None,
    frequency: str = None,
):
    """수집값 저장. API 실패 시 전일값으로 대체하되 is_stale=1 로 표시.
    date_str 미지정 시 매번 date.today()를 계산한다 (TODAY_ISO 전역 상수 제거).
    """
    store_date = date_str or date.today().isoformat()
    is_stale = 0
    if value is None:
        fallback = get_previous_value(indicator, db_path=DB_PATH)
        logger.warning(f"[{indicator}] 수집 실패 -> 전일값 대체(stale): {fallback}")
        log_collect(indicator, "fail", "전일값 대체", db_path=DB_PATH)
        value = fallback
        is_stale = 1
    else:
        log_collect(indicator, "success", db_path=DB_PATH)

    if value is not None:
        try:
            upsert_indicator(
                store_date, indicator, float(value), source, unit,
                db_path=DB_PATH, is_stale=is_stale, frequency=frequency,
            )
            stale_tag = " [STALE]" if is_stale else ""
            logger.info(f"  [{indicator}] {float(value):.4f} {unit} ({store_date}){stale_tag} 저장 완료")
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
    logger.info(f"데이터 수집 시작: {date.today().isoformat()}")
    clear_api_errors()  # 이전 실행 오류 초기화
    meta = load_indicator_meta()

    # ── 한국은행 ECOS KeyStatisticList (월/분기 지표) ───────────────
    logger.info("[ECOS] KeyStatisticList 수집 중...")
    ecos_indicators = indicators_by_source("ecos_keystat", meta)
    keystat = {}
    with collector_run("ecos_keystat") as record:
        keystat = fetch_ecos_keystat(db_path=DB_PATH)
        if keystat:
            logger.info(f"[ECOS] {len(keystat)}개 지표 수신")
        else:
            logger.error("[ECOS] KeyStatisticList 수집 완전 실패")
        for ind_key, ind_meta in ecos_indicators.items():
            kor_name = ind_meta.get("symbol")
            item = keystat.get(kor_name) if kor_name else None
            val = item["value"] if item else None
            safe_store(
                ind_key,
                val,
                "ECOS:KeyStatisticList",
                ind_meta.get("unit", ""),
                frequency=ind_meta.get("frequency"),
            )
            record(success=val is not None)

    # ── Yahoo Finance 실시간 가격 (KOSPI/KOSDAQ/금/두바이유) ─────────
    logger.info("[Yahoo] 실시간 가격 수집 중 (KOSPI/KOSDAQ/GOLD/DUBAI_OIL + 섹터ETF)...")
    yahoo_indicators = indicators_by_source("yahoo_quote", meta)
    with collector_run("yahoo_quote") as record:
        for ind_key, ind_meta in yahoo_indicators.items():
            symbol = ind_meta.get("symbol")
            result = fetch_yahoo_quote(symbol, db_path=DB_PATH) if symbol else None
            if result:
                actual_date, val = result
                safe_store(
                    ind_key,
                    val,
                    f"Yahoo:{symbol}",
                    ind_meta.get("unit", ""),
                    date_str=actual_date,
                    frequency=ind_meta.get("frequency"),
                )
                record(success=True)
            else:
                safe_store(ind_key, None, f"Yahoo:{symbol}", ind_meta.get("unit", ""), frequency=ind_meta.get("frequency"))
                record(success=False)

    # ── FRED 미국 지표 ──────────────────────────────────────────────
    logger.info("[FRED] 미국 경제지표 수집 중...")

    with collector_run("fred") as record:
        for ind_key, ind_meta in indicators_by_source("fred", meta).items():
            series_id = ind_meta.get("symbol")
            obs = fetch_fred(series_id, db_path=DB_PATH) if series_id else []
            latest = _fred_date_val(obs)
            if latest:
                obs_date, val = latest
                safe_store(
                    ind_key,
                    val,
                    f"FRED:{series_id}",
                    ind_meta.get("unit", ""),
                    date_str=obs_date,
                    frequency=ind_meta.get("frequency"),
                )
                record(success=True)
            else:
                safe_store(ind_key, None, f"FRED:{series_id}", ind_meta.get("unit", ""), frequency=ind_meta.get("frequency"))
                record(success=False)

    # WTI/US10Y처럼 시장 데이터와 공식 FRED 데이터 중 더 최신 관측치를 선택하는 지표
    with collector_run("hybrid_market_fred") as record:
        for ind_key, ind_meta in indicators_by_source("hybrid_market_fred", meta).items():
            yahoo_symbol = ind_meta.get("symbol")
            fred_symbol = ind_meta.get("fred_symbol")
            fred_obs = fetch_fred(fred_symbol, db_path=DB_PATH) if fred_symbol else []
            fred_latest = _fred_date_val(fred_obs)
            yahoo_latest = fetch_yahoo_quote(yahoo_symbol, db_path=DB_PATH) if yahoo_symbol else None
            if yahoo_latest and (fred_latest is None or yahoo_latest[0] >= fred_latest[0]):
                val = yahoo_latest[1]
                if ind_key == "US10Y" and val > 10:
                    val = val / 10
                safe_store(
                    ind_key,
                    val,
                    f"Yahoo:{yahoo_symbol}",
                    ind_meta.get("unit", ""),
                    date_str=yahoo_latest[0],
                    frequency=ind_meta.get("frequency"),
                )
                record(success=True)
            elif fred_latest:
                safe_store(
                    ind_key,
                    fred_latest[1],
                    f"FRED:{fred_symbol}",
                    ind_meta.get("unit", ""),
                    date_str=fred_latest[0],
                    frequency=ind_meta.get("frequency"),
                )
                record(success=True)
            else:
                safe_store(ind_key, None, f"FRED:{fred_symbol}", ind_meta.get("unit", ""), frequency=ind_meta.get("frequency"))
                record(success=False)

    # ── NY Fed 공급망 압력지수 (GSCPI · PMI Supplier Delivery Times 기반) ────
    logger.info("[NY Fed] 공급망 압력지수(GSCPI/PMI 기반) 수집 중...")
    with collector_run("nyfed_gscpi") as record:
        for ind_key, ind_meta in indicators_by_source("nyfed_gscpi", meta).items():
            pmi_sdt_val = fetch_nyfed_pmi_sdt(db_path=DB_PATH)
            if pmi_sdt_val is not None:
                safe_store(
                    ind_key,
                    pmi_sdt_val,
                    "NY_FED:GSCPI",
                    ind_meta.get("unit", ""),
                    frequency=ind_meta.get("frequency"),
                )
                record(success=True)
            else:
                logger.info("[NY Fed] GSCPI 수집 실패 - 건너뜀")
                safe_store(ind_key, None, "NY_FED:GSCPI", ind_meta.get("unit", ""), frequency=ind_meta.get("frequency"))
                record(success=False)

    # ── CapEx (AI 병목 + 전력 병목) ─────────────────────────────────
    logger.info("[FMP] CapEx 수집 중 (AI hyperscaler + Utility)...")
    with collector_run("fmp_capex") as record:
        for ind_key, ind_meta in indicators_by_source("fmp_capex", meta).items():
            ticker = ind_meta.get("symbol") or ind_key.replace("CAPEX_", "")
            rows = fetch_fmp_capex(ticker, limit=5, db_path=DB_PATH)
            for row in rows:
                date_str = row["date"]
                capex_b  = row["capex_b"]
                try:
                    upsert_indicator(
                        date_str,
                        ind_key,
                        capex_b,
                        f"FMP:{ticker}",
                        ind_meta.get("unit", "B USD"),
                        db_path=DB_PATH,
                        frequency=ind_meta.get("frequency", "quarterly"),
                        observed_date=date_str,
                    )
                except Exception as e:
                    logger.error(f"  [{ind_key}@{date_str}] 저장 오류: {e}")
            if rows:
                latest = rows[0]
                logger.info(f"  [{ind_key}] 최신: {latest['date']} = ${latest['capex_b']:.2f}B ({len(rows)}분기 저장)")
                log_collect(ind_key, "success", db_path=DB_PATH)
                record(success=True)
            else:
                safe_store(ind_key, None, f"FMP:{ticker}", ind_meta.get("unit", "B USD"), frequency=ind_meta.get("frequency", "quarterly"))
                record(success=False)
            time.sleep(0.3)

    # ── 전력 병목: ERCOT/PJM 부하·예비율 ────────────────────────────
    logger.info("[Power] ERCOT/PJM 전력 병목 데이터 수집 중...")
    with collector_run("power_grid") as record:
        ercot = fetch_ercot_grid_status(db_path=DB_PATH)
        ercot_map = {
            "ERCOT_LOAD_MW": "load_mw",
            "ERCOT_RESERVE_MARGIN": "reserve_margin_pct",
        }
        for ind_key, field in ercot_map.items():
            ind_meta = meta.get(ind_key, {})
            val = ercot.get(field) if ercot else None
            safe_store(
                ind_key,
                val,
                ercot.get("source", "ERCOT:supply-demand") if ercot else "ERCOT:supply-demand",
                ind_meta.get("unit", ""),
                frequency=ind_meta.get("frequency", "daily"),
            )
            record(success=val is not None)

        pjm = fetch_pjm_load(db_path=DB_PATH)
        pjm_meta = meta.get("PJM_LOAD_MW", {})
        pjm_val = pjm.get("load_mw") if pjm else None
        safe_store(
            "PJM_LOAD_MW",
            pjm_val,
            pjm.get("source", "PJM:inst_load") if pjm else "PJM:inst_load",
            pjm_meta.get("unit", "MW"),
            frequency=pjm_meta.get("frequency", "daily"),
        )
        record(success=pjm_val is not None)

    # ── 상대강도 파생 지표 (P2: SMH/SPY, XLU/SPY) ──────────────────
    logger.info("[RS] 섹터 상대강도 계산 중...")
    try:
        from transforms.relative_strength import compute_relative_strength
        for rs_key, num_key, den_key in [
            ("RS_SMH_SPY", "SMH", "SPY"),
            ("RS_XLU_SPY", "XLU", "SPY"),
        ]:
            rs = compute_relative_strength(num_key, den_key, db_path=DB_PATH)
            if rs is not None:
                today_str = date.today().isoformat()
                upsert_indicator(today_str, rs_key, rs, f"derived:{num_key}/{den_key}", "ratio",
                                 db_path=DB_PATH, frequency="daily")
                logger.info(f"  [{rs_key}] {rs:.4f}")
    except Exception as e:
        logger.warning(f"[RS] 상대강도 계산 실패: {e}")

    # ── Naver 뉴스 헤드라인 (선택) ──────────────────────────────────
    try:
        news = fetch_naver_news("경제 인플레이션", display=5)
        if news:
            logger.info(f"[NAVER] 뉴스 {len(news)}건 수집")
    except Exception as e:
        logger.warning(f"[NAVER] 수집 건너뜀: {e}")

    logger.info("=" * 60)
    logger.info("전체 수집 완료")

    # ── API 인증/만료 오류 텔레그램 알림 ────────────────────────────
    errors = get_api_errors()
    if errors:
        logger.warning(f"[API 오류] {len(errors)}개 API 인증 오류 발생 → 텔레그램 알림 전송")
        send_api_alert(errors)

    # ── 기술적 지표 피처 계산 + 매매 신호 생성 ───────────────────────
    logger.info("[Quant] 기술적 지표 피처 계산 및 매매 신호 생성 중...")
    try:
        from transforms.technical_indicators import compute_all_features
        from strategies import run_all_strategies
        from database import save_features, save_signal, mark_signal_notified

        # 주요 지표 피처 저장
        for ind in ["KOSPI", "KOSDAQ", "GOLD", "WTI", "USD_KRW", "US500", "SMH", "SPY"]:
            features = compute_all_features(ind, DB_PATH)
            if features:
                save_features(features, DB_PATH)
                logger.info(
                    f"  [{ind}] RSI={features.get('rsi14')}, "
                    f"MA={features.get('ma_signal')}, MACD={features.get('macd_bias')}"
                )

        # 전략 실행 → 신호 생성 → DB 저장 → 텔레그램 전송
        signals = run_all_strategies(db_path=DB_PATH)
        if signals:
            stored_signals = []
            for sig in signals:
                sid = save_signal(
                    indicator=sig["indicator"],
                    signal_type=sig["signal_type"],
                    strategy=sig["strategy"],
                    confidence=sig["confidence"],
                    price=sig.get("price"),
                    detail=sig.get("detail"),
                    db_path=DB_PATH,
                )
                stored_signals.append({**sig, "_id": sid})
            n_sent = send_signal_alerts(signals)
            for sig in stored_signals:
                mark_signal_notified(sig["_id"], DB_PATH)
            logger.info(f"[Quant] 신호 {len(signals)}건 생성, {n_sent}건 텔레그램 전송 완료")
        else:
            logger.info("[Quant] 매매 신호 없음")
    except Exception as e:
        logger.error(f"[Quant] 피처/신호 계산 오류: {e}")


if __name__ == "__main__":
    validate_config()
    init_db(DB_PATH)
    collect_all_indicators()
    summary = build_summary(db_path=DB_PATH)
    send_report(db_path=DB_PATH)
    alert_if_fail(db_path=DB_PATH)

    # ── IR 스크래핑 및 Gemini 요약 (AI 병목 레이어 포함) ───────────
    # AI 병목: MSFT/AMZN/META/GOOGL + NVDA/TSMC/Micron/SK하이닉스/삼성
    logger.info("[IR] 신규 8-K/20-F 파일링 확인 중...")
    try:
        from ir_scraper import get_new_filings, fetch_filing_text, count_ai_bottleneck_keywords
        from gemini_client import summarize_ir
        from database import save_ir_filing, save_ir_keyword_mentions

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
                    keyword_counts = count_ai_bottleneck_keywords(text)
                    summary_text = summarize_ir(f["company"], f["date"], text)
                    save_ir_filing(f, summary_text, db_path=DB_PATH)
                    save_ir_keyword_mentions(f, keyword_counts, db_path=DB_PATH)
                    summarized.append({**f, "summary": summary_text})
                    logger.info(f"[IR] 요약 완료: {f['ticker']} {f['date']}")
                except Exception as e:
                    logger.error(f"[IR] 오류 ({f['ticker']} {f['date']}): {e}")

            send_ir_summaries(summarized)
            logger.info(f"[IR] 텔레그램 전송 완료: {len(summarized)}건")

    except Exception as e:
        logger.error(f"[IR] 전체 플로우 오류: {e}")
