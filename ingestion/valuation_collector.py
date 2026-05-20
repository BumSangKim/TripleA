# ingestion/valuation_collector.py
# 기업 밸류에이션 데이터 수집
#
# 소스:
#   1. Yahoo Finance quoteSummary API  — 실시간 시장 멀티플 (EV/EBITDA, P/E, P/B)
#   2. FMP key-metrics API            — 분기별 ROIC, Revenue Growth, EBITDA Margin
#
# 커버리지:
#   US: MSFT, GOOGL, META, AMZN, NVDA, SMH (ETF proxy for semis)
#   KR: 005930.KS(Samsung), 000660.KS(SK Hynix), 005380.KS(Hyundai), 005490.KS(POSCO)

import logging
import time
from datetime import date
from typing import Any

import requests

from config import FMP_KEY
from storage.database import (
    DB_PATH,
    upsert_company_fundamentals,
    upsert_company_multiples,
)

logger = logging.getLogger(__name__)

# ── 커버리지 정의 ───────────────────────────────────────────────────────────────

TICKER_META: dict[str, dict] = {
    # US 테크 성장주
    "MSFT":      {"name": "Microsoft",         "sector": "tech_growth",   "country": "US"},
    "GOOGL":     {"name": "Alphabet",           "sector": "tech_growth",   "country": "US"},
    "META":      {"name": "Meta Platforms",     "sector": "tech_growth",   "country": "US"},
    "AMZN":      {"name": "Amazon",             "sector": "tech_growth",   "country": "US"},
    # 반도체
    "NVDA":      {"name": "NVIDIA",             "sector": "semiconductor", "country": "US"},
    "005930.KS": {"name": "Samsung Electronics","sector": "semiconductor", "country": "KR"},
    "000660.KS": {"name": "SK Hynix",           "sector": "semiconductor", "country": "KR"},
    # 자동차
    "005380.KS": {"name": "Hyundai Motor",      "sector": "auto",          "country": "KR"},
    # 소재
    "005490.KS": {"name": "POSCO Holdings",     "sector": "materials",     "country": "KR"},
}


# ── Yahoo Finance quoteSummary ──────────────────────────────────────────────

_YF_HEADERS = {"User-Agent": "Mozilla/5.0"}
_YF_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
_YF_MODULES = "financialData,defaultKeyStatistics,summaryDetail"


def fetch_yahoo_multiples(ticker: str) -> dict[str, Any]:
    """
    Yahoo Finance quoteSummary로 현재 시장 멀티플 수집.

    Returns
    -------
    dict with keys:
        close_price, market_cap, enterprise_value,
        ev_ebitda, pe_ratio, pb_ratio, ps_ratio,
        revenue_growth, operating_margin, roe
    """
    url = _YF_URL.format(ticker=ticker)
    try:
        r = requests.get(
            url,
            params={"modules": _YF_MODULES},
            headers=_YF_HEADERS,
            timeout=15,
        )
        r.raise_for_status()
    except Exception as e:
        logger.warning("[ValCollector] %s Yahoo quoteSummary 실패: %s", ticker, e)
        return {}

    try:
        result = r.json().get("quoteSummary", {}).get("result", [{}])[0]
    except Exception:
        return {}

    fin = result.get("financialData", {})
    stats = result.get("defaultKeyStatistics", {})
    summ = result.get("summaryDetail", {})

    def _raw(d: dict, key: str) -> float | None:
        val = d.get(key)
        if isinstance(val, dict):
            v = val.get("raw")
            return float(v) if v is not None else None
        return float(val) if val is not None else None

    return {
        "close_price":      _raw(fin, "currentPrice") or _raw(summ, "regularMarketPrice"),
        "market_cap":       (_raw(summ, "marketCap") or _raw(stats, "marketCap") or 0) / 1e9,
        "enterprise_value": (_raw(stats, "enterpriseValue") or 0) / 1e9,
        "ev_ebitda":        _raw(stats, "enterpriseToEbitda"),
        "pe_ratio":         _raw(summ, "trailingPE") or _raw(stats, "trailingPE"),
        "pb_ratio":         _raw(stats, "priceToBook"),
        "ps_ratio":         _raw(stats, "priceToSalesTrailing12Months"),
        "revenue_growth":   (_raw(fin, "revenueGrowth") or 0) * 100,     # YoY %
        "operating_margin": (_raw(fin, "operatingMargins") or 0) * 100,  # %
        "ebitda_margin":    (_raw(fin, "ebitdaMargins") or 0) * 100 if fin.get("ebitdaMargins") else None,
        "roe":              (_raw(fin, "returnOnEquity") or 0) * 100,
    }


# ── FMP key-metrics (분기별 펀더멘털) ──────────────────────────────────────────

_FMP_URL = "https://financialmodelingprep.com/stable/key-metrics"


def fetch_fmp_fundamentals(ticker: str, limit: int = 8) -> list[dict]:
    """
    FMP key-metrics로 분기별 ROIC, Revenue Growth, EBITDA Margin 수집.

    Returns list of quarter dicts (most recent first).
    """
    if not FMP_KEY:
        logger.debug("[ValCollector] FMP_API_KEY 없음 — 분기 펀더멘털 수집 건너뜀")
        return []

    # KR 티커를 FMP 포맷으로 변환 (005930.KS → 005930.KS or just skip if not available)
    fmp_ticker = ticker  # FMP generally supports Yahoo-style tickers
    try:
        r = requests.get(
            _FMP_URL,
            params={"symbol": fmp_ticker, "apikey": FMP_KEY, "period": "quarter", "limit": limit},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.warning("[ValCollector] %s FMP 펀더멘털 실패: %s", ticker, e)
        return []

    if not isinstance(data, list):
        logger.debug("[ValCollector] %s FMP 비정상 응답: %s", ticker, str(data)[:80])
        return []

    results = []
    for item in data:
        period = item.get("date", "")
        if not period:
            continue
        results.append({
            "period":           period,
            "roic":             _safe_pct(item.get("roic")),
            "roe":              _safe_pct(item.get("roe")),
            "revenue_growth_yoy": _safe_pct(item.get("revenueGrowth")),
            "ebitda_margin":    _safe_pct(item.get("ebitdaMargin")),
            "debt_ratio":       float(item["debtToEquity"]) if item.get("debtToEquity") else None,
        })
    return results


def _safe_pct(v) -> float | None:
    """비율(0~1 범위) → % 변환. 이미 % 단위이면 그대로."""
    if v is None:
        return None
    f = float(v)
    # FMP는 보통 소수 단위(0.25 = 25%), abs > 3 이면 이미 % 단위로 간주
    if abs(f) <= 3.0:
        return f * 100.0
    return f


# ── 통합 수집 함수 ──────────────────────────────────────────────────────────────

def collect_all_valuation_data(db_path: str = DB_PATH) -> int:
    """
    모든 커버리지 티커의 시장 멀티플 + 분기 펀더멘털 수집 후 DB 저장.

    Returns
    -------
    int : 성공적으로 저장된 티커 수
    """
    today = date.today().isoformat()
    success = 0

    for ticker, meta in TICKER_META.items():
        try:
            # ── 시장 멀티플 수집 ────────────────────────────────────
            mults = fetch_yahoo_multiples(ticker)
            if not mults:
                logger.warning("[ValCollector] %s 멀티플 수집 실패", ticker)
                continue

            # EV/EBITDA 와 P/E 중 하나는 있어야 저장 의미 있음
            if mults.get("ev_ebitda") is None and mults.get("pe_ratio") is None:
                logger.warning("[ValCollector] %s 주요 멀티플 없음 — 건너뜀", ticker)
                continue

            upsert_company_multiples(
                date_str=today,
                ticker=ticker,
                sector=meta["sector"],
                close_price=mults.get("close_price"),
                market_cap=mults.get("market_cap"),
                enterprise_value=mults.get("enterprise_value"),
                ev_ebitda=mults.get("ev_ebitda"),
                pe_ratio=mults.get("pe_ratio"),
                pb_ratio=mults.get("pb_ratio"),
                ps_ratio=mults.get("ps_ratio"),
                db_path=db_path,
            )
            logger.info(
                "[ValCollector] %s 멀티플 저장 (EV/EBITDA=%.1fx, PE=%.1f, PB=%.2f)",
                ticker,
                mults.get("ev_ebitda") or 0,
                mults.get("pe_ratio") or 0,
                mults.get("pb_ratio") or 0,
            )

            # ── FMP 분기 펀더멘털 수집 (ebitda_margin이 Yahoo에 없을 경우 보완) ─
            fmp_records = fetch_fmp_fundamentals(ticker, limit=8)
            for rec in fmp_records:
                ebitda_m = rec.get("ebitda_margin") or mults.get("ebitda_margin") or mults.get("operating_margin")
                upsert_company_fundamentals(
                    ticker=ticker,
                    period=rec["period"],
                    roic=rec.get("roic"),
                    roe=rec.get("roe") or (mults.get("roe") if rec == fmp_records[0] else None),
                    revenue_growth_yoy=rec.get("revenue_growth_yoy")
                        or (mults.get("revenue_growth") if rec == fmp_records[0] else None),
                    ebitda_margin=ebitda_m,
                    debt_ratio=rec.get("debt_ratio"),
                    db_path=db_path,
                )
            if fmp_records:
                logger.info("[ValCollector] %s 분기 펀더멘털 %d건 저장", ticker, len(fmp_records))

            success += 1
            time.sleep(0.3)  # API 과부하 방지

        except Exception as e:
            logger.error("[ValCollector] %s 수집 오류: %s", ticker, e)

    logger.info("[ValCollector] 완료: %d/%d 티커 성공", success, len(TICKER_META))
    return success
