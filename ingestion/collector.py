# collector.py
# 각 데이터 소스에서 경제 지표를 수집하는 모듈
# ECOS StatisticSearch 대신 KeyStatisticList 사용 (더 안정적)
import re

import requests
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from config import ECOS_KEY, FRED_KEY, FMP_KEY, NAVER_ID, NAVER_SECRET, KIPRIS_KEY, KIS_APP_KEY, KIS_APP_SECRET, KIS_ISDEMO
from storage.database import DB_PATH as DEFAULT_DB_PATH, mask_sensitive_url, save_raw_observation

logger = logging.getLogger(__name__)

# 수집 실행 중 발생한 API 인증/만료 오류를 누적 (키: API 이름, 값: 오류 상세)
_api_errors: dict[str, str] = {}


def get_api_errors() -> dict[str, str]:
    """현재까지 누적된 API 인증/만료 오류 반환"""
    return dict(_api_errors)


def clear_api_errors() -> None:
    """누적 오류 초기화 (매 파이프라인 실행 시작 시 호출)"""
    _api_errors.clear()


def _record_auth_error(api_name: str, detail: str) -> None:
    """401/403 등 인증 오류 기록"""
    _api_errors[api_name] = detail
    logger.error(f"[API 인증 오류] {api_name}: {detail}")


def get_session() -> requests.Session:
    """재시도 로직이 포함된 HTTP 세션 반환"""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=2,  # 1초 → 2초 → 4초 대기
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _masked_url(url: str, *secrets: str | None) -> str:
    masked = url
    for secret in secrets:
        if secret:
            masked = masked.replace(secret, "***MASKED***")
    return masked


def _save_raw(source: str, raw_data, indicator: str = None, obs_date: str = None, db_path: str = None) -> None:
    """원본 응답 저장 실패가 수집 실패로 전파되지 않도록 격리한다."""
    try:
        save_raw_observation(
            source=source,
            raw_data=raw_data,
            indicator=indicator,
            obs_date=obs_date,
            db_path=db_path or DEFAULT_DB_PATH,
        )
    except Exception as e:
        logger.warning(f"[raw_observations] 저장 실패 ({source}): {e}")


def _sanitize_error(e: Exception) -> str:
    return mask_sensitive_url(str(e))


def fetch_ecos_keystat(db_path: str = None) -> dict:
    """
    ECOS KeyStatisticList API 호출 - 한국은행 핵심 경제지표 전체 조회
    StatisticSearch보다 안정적이며 CPI, PPI, 환율, 금리, 코스피, 실업률, 두바이유, 금 등 포함
    반환: {지표명: {'value': float, 'unit': str}}
    """
    url = f"https://ecos.bok.or.kr/api/KeyStatisticList/{ECOS_KEY}/json/kr/1/200/"
    session = get_session()
    try:
        res = session.get(url, timeout=10)
        if res.status_code in (401, 403):
            _record_auth_error("ECOS", f"HTTP {res.status_code} - API 키 만료 또는 인증 실패")
            return {}
        res.raise_for_status()
        data = res.json()
        _save_raw(
            "ECOS:KeyStatisticList",
            {"url": _masked_url(url, ECOS_KEY), "status_code": res.status_code, "response": data},
            db_path=db_path,
        )
        # ECOS는 인증 오류 시 HTTP 200 + RESULT.CODE="ERROR-300" 반환
        err_code = data.get("RESULT", {}).get("CODE", "")
        if err_code and err_code.startswith("ERROR"):
            _record_auth_error("ECOS", f"응답 오류 코드 {err_code}: {data.get('RESULT',{}).get('MESSAGE','')}")
            return {}
        rows = data.get("KeyStatisticList", {}).get("row", [])
        result = {}
        for row in rows:
            name = row.get("KEYSTAT_NAME", "").strip()
            val = row.get("DATA_VALUE", "")
            unit = row.get("UNIT_NAME", "")
            try:
                result[name] = {"value": float(str(val).replace(",", "")), "unit": unit}
            except (ValueError, TypeError):
                pass
        return result
    except Exception as e:
        logger.error(f"[ECOS KeyStatisticList] 수집 실패: {_sanitize_error(e)}")
        return {}


def fetch_dxy_yahoo() -> float | None:
    """
    Yahoo Finance에서 실제 DXY (ICE US Dollar Index, DX-Y.NYB) 수집
    DTWEXBGS(달러 무역가중지수)와 구별되는 ICE 기준 달러인덱스
    반환: 최신 종가 (float) 또는 None
    """
    val = fetch_yahoo_quote("DX-Y.NYB")
    return val[1] if val else None


def fetch_yahoo_quote(symbol: str, db_path: str = None) -> tuple[str, float] | None:
    """
    Yahoo Finance에서 최신 종가와 실제 날짜를 함께 반환
    반환: (날짜 "YYYY-MM-DD", 종가) 또는 None

    전략:
    1) meta.regularMarketPrice + 거래소 로컬 타임존으로 가장 최신 날짜를 구함
    2) 완전한 일봉 close(None이 아닌 값)의 날짜와 비교
    3) regularMarketPrice 날짜가 더 최신이면 사용, 아니면 일봉 close 사용
       → Yahoo가 당일 일봉 close를 아직 확정하지 않아 None을 반환하는 경우 대응
    """
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    headers = {"User-Agent": "Mozilla/5.0"}
    session = get_session()
    try:
        res = session.get(
            url,
            params={"range": "5d", "interval": "1d"},
            headers=headers,
            timeout=10,
        )
        res.raise_for_status()
        data = res.json()
        _save_raw(
            f"Yahoo:{symbol}",
            {
                "url": url,
                "params": {"range": "5d", "interval": "1d"},
                "status_code": res.status_code,
                "response": data,
            },
            obs_date=None,
            db_path=db_path,
        )
        result = data.get("chart", {}).get("result", [{}])[0]
        meta   = result.get("meta", {})
        closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        timestamps = result.get("timestamp", [])

        # ── 일봉 데이터에서 가장 최근 유효 close ──────────────────────
        last_daily_date  = None
        last_daily_price = None
        for ts, val in zip(reversed(timestamps), reversed(closes)):
            if val is not None:
                last_daily_date  = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                last_daily_price = float(val)
                break

        # ── meta.regularMarketPrice (거래소 타임존 기반 날짜) ─────────
        rm_price = meta.get("regularMarketPrice")
        rm_time  = meta.get("regularMarketTime")
        tz_name  = meta.get("exchangeTimezoneName", "UTC")
        rm_date  = None

        if rm_price and rm_time:
            try:
                exchange_tz = ZoneInfo(tz_name)
            except (ZoneInfoNotFoundError, KeyError):
                exchange_tz = timezone.utc
            rm_date = (
                datetime.fromtimestamp(rm_time, tz=timezone.utc)
                .astimezone(exchange_tz)
                .strftime("%Y-%m-%d")
            )

        # ── 더 최신인 소스 선택 ───────────────────────────────────────
        if rm_date and rm_price:
            if last_daily_date is None or rm_date > last_daily_date:
                logger.info(f"[Yahoo {symbol}] regularMarketPrice {rm_date} = {rm_price:.4f} (tz={tz_name})")
                return (rm_date, float(rm_price))

        if last_daily_price is not None:
            logger.info(f"[Yahoo {symbol}] 일봉 {last_daily_date} = {last_daily_price:.4f}")
            return (last_daily_date, last_daily_price)

        logger.warning(f"[Yahoo {symbol}] 유효 데이터 없음")
        return None
    except Exception as e:
        logger.error(f"[Yahoo {symbol}] 수집 실패: {_sanitize_error(e)}")
        return None


def fetch_fmp_capex(ticker: str, limit: int = 5, db_path: str = None) -> list[dict]:
    """
    Financial Modeling Prep API - 분기별 CapEx 수집
    Hyperscaler AI CapEx 신호 (Deep Research S1): MSFT, GOOGL, META, AMZN
    반환: [{"date": "2026-03-31", "capex_b": 30.88, "ticker": "MSFT"}, ...]
           capex_b는 십억 달러(Billion USD) 기준 (양수)
    limit: 최대 5 (FMP 무료 플랜 제한)
    """
    if not FMP_KEY:
        logger.warning("[FMP] FMP_API_KEY 미설정 - CapEx 수집 건너뜀")
        return fetch_sec_capex(ticker, limit=limit, db_path=db_path)
    limit = min(limit, 5)  # 무료 플랜 최대 5
    session = get_session()
    try:
        res = session.get(
            "https://financialmodelingprep.com/stable/cash-flow-statement",
            params={
                "symbol": ticker,
                "apikey": FMP_KEY,
                "limit": limit,
                "period": "quarter",
            },
            timeout=15,
        )
        if res.status_code in (401, 403):
            _record_auth_error("FMP", f"{ticker}: HTTP {res.status_code} - API 키 만료 또는 플랜 초과")
            return []
        if res.status_code == 402:
            logger.warning(f"[FMP] {ticker} 무료 플랜 제한(402) - SEC companyfacts fallback 시도")
            return fetch_sec_capex(ticker, limit=limit, db_path=db_path)
        res.raise_for_status()
        if not res.text:
            logger.warning(f"[FMP] {ticker} 빈 응답")
            return []
        data = res.json()
        _save_raw(
            f"FMP:{ticker}",
            {
                "url": "https://financialmodelingprep.com/stable/cash-flow-statement",
                "params": {
                    "symbol": ticker,
                    "apikey": FMP_KEY,
                    "limit": limit,
                    "period": "quarter",
                },
                "status_code": res.status_code,
                "response": data,
            },
            indicator=f"CAPEX_{ticker}",
            db_path=db_path,
        )
        # FMP는 인증 실패 시 {"Error Message": "..."} 형태로 반환
        if isinstance(data, dict) and ("Error Message" in data or "message" in data):
            msg = data.get("Error Message") or data.get("message", "알 수 없는 오류")
            if any(kw in msg.lower() for kw in ("invalid", "not authorized", "premium", "limit")):
                _record_auth_error("FMP", f"{ticker}: {msg}")
            return fetch_sec_capex(ticker, limit=limit, db_path=db_path)
        if not isinstance(data, list):
            logger.warning(f"[FMP] {ticker} 예상치 못한 응답: {str(data)[:80]}")
            return []
        result = []
        for item in data:
            raw = item.get("capitalExpenditure", 0) or 0
            result.append({
                "date": item.get("date", ""),
                "capex_b": round(abs(raw) / 1e9, 3),
                "ticker": ticker,
            })
        logger.info(f"[FMP] {ticker} CapEx {len(result)}분기 수집 완료")
        return result
    except Exception as e:
        logger.error(f"[FMP] {ticker} 수집 실패: {_sanitize_error(e)}")
        return fetch_sec_capex(ticker, limit=limit, db_path=db_path)


SEC_CAPEX_CIKS = {
    "NEE": "0000753308",
    "DUK": "0001326160",
    "SO": "0000092122",
}


def fetch_sec_capex(ticker: str, limit: int = 5, db_path: str = None) -> list[dict]:
    """SEC companyfacts 기반 CapEx fallback. API 키 없이 유틸리티 CapEx를 보강한다."""
    cik = SEC_CAPEX_CIKS.get(ticker)
    if not cik:
        return []
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    headers = {"User-Agent": "TripleA Pipeline bumsangkim@dev.io"}
    session = get_session()
    try:
        res = session.get(url, headers=headers, timeout=20)
        res.raise_for_status()
        data = res.json()
        _save_raw(
            f"SEC:{ticker}:companyfacts",
            {"url": url, "status_code": res.status_code, "response": data},
            indicator=f"CAPEX_{ticker}",
            db_path=db_path,
        )
        facts = data.get("facts", {}).get("us-gaap", {})
        for key in (
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "CapitalExpendituresIncurredButNotYetPaid",
            "PaymentsToAcquireProductiveAssets",
            "PaymentsToAcquireOtherPropertyPlantAndEquipment",
        ):
            units = facts.get(key, {}).get("units", {})
            rows = units.get("USD", [])
            quarterly = [
                row for row in rows
                if row.get("form") in ("10-Q", "10-K")
                and row.get("start")
                and row.get("end")
                and row.get("val") is not None
                and _months_between(row["start"], row["end"]) <= 4
            ]
            if quarterly:
                latest = sorted(quarterly, key=lambda x: (x.get("end", ""), x.get("filed", "")), reverse=True)
                result = [
                    {
                        "date": row["end"],
                        "capex_b": round(abs(float(row["val"])) / 1e9, 3),
                        "ticker": ticker,
                    }
                    for row in latest[:limit]
                ]
                logger.info(f"[SEC] {ticker} CapEx {len(result)}분기 수집 완료 ({key})")
                return result
        logger.warning(f"[SEC] {ticker} CapEx 태그를 찾지 못함")
    except Exception as e:
        logger.warning(f"[SEC] {ticker} CapEx fallback 실패: {_sanitize_error(e)}")
    return []


def _months_between(start: str, end: str) -> int:
    try:
        start_y, start_m = [int(x) for x in start[:7].split("-")]
        end_y, end_m = [int(x) for x in end[:7].split("-")]
        return (end_y - start_y) * 12 + (end_m - start_m) + 1
    except Exception:
        return 999


def fetch_nyfed_pmi_sdt(db_path: str = None) -> float | None:
    """
    NY Fed 글로벌 공급망 압력지수(GSCPI) 수집
    PMI Supplier Delivery Times를 핵심 입력으로 사용하는 공급망 압력 종합지수
    출처: https://www.newyorkfed.org/research/policy/gscpi
    반환: 최신 GSCPI 값 (float) 또는 None
    """
    url = (
        "https://www.newyorkfed.org/medialibrary/research/interactives/"
        "gscpi/downloads/gscpi_data.xlsx"
    )
    session = get_session()
    try:
        res = session.get(url, timeout=15)
        res.raise_for_status()
        # 파일이 OLE2(.xls) 형식이므로 xlrd로 파싱
        try:
            import xlrd
        except ImportError as e:
            logger.error("[NY Fed GSCPI] xlrd 패키지 필요: pip install xlrd")
            raise e
        wb = xlrd.open_workbook(file_contents=res.content)
        sh = wb.sheet_by_name("GSCPI Monthly Data")
        # 마지막 유효 행에서 GSCPI 값(B열, 인덱스 1) 추출
        for r_idx in range(sh.nrows - 1, 0, -1):
            val = sh.cell(r_idx, 1).value
            if val and isinstance(val, (int, float)):
                date_str = sh.cell(r_idx, 0).value
                _save_raw(
                    "NY_FED:GSCPI",
                    {
                        "url": url,
                        "status_code": res.status_code,
                        "content_length": len(res.content),
                        "sheet": "GSCPI Monthly Data",
                        "latest": {"date": date_str, "value": float(val)},
                    },
                    indicator="PMI_SDT",
                    obs_date=str(date_str),
                    db_path=db_path,
                )
                logger.info(f"[NY Fed GSCPI] 최신값: {date_str} = {val:.4f}")
                return float(val)
        logger.warning("[NY Fed GSCPI] 유효 데이터 행 없음")
        return None
    except Exception as e:
        logger.error(f"[NY Fed GSCPI] 수집 실패: {_sanitize_error(e)}")
        return None


def fetch_ecos_statistic_search(
    stat_id: str,
    freq: str,
    start: str,
    end: str,
    item_code: str = "",
) -> list:
    """
    한국은행 ECOS StatisticSearch API 호출
    주의: API 불안정이 잦으므로 KeyStatisticList(fetch_ecos_keystat) 사용 권장
    freq: 'DD'(일), 'MM'(월), 'QQ'(분기)
    item_code: 세부 항목 코드 (생략 가능)
    반환: row 리스트 [{"TIME": "...", "DATA_VALUE": "..."}, ...]
    """
    suffix = f"/{item_code}" if item_code else "/"
    url = (
        f"https://ecos.bok.or.kr/api/StatisticSearch/{ECOS_KEY}"
        f"/json/kr/1/100/{stat_id}/{freq}/{start}/{end}{suffix}"
    )
    session = get_session()
    try:
        res = session.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        rows = data.get("StatisticSearch", {}).get("row", [])
        return rows
    except Exception as e:
        logger.error(f"[ECOS StatisticSearch] {stat_id} 수집 실패: {_sanitize_error(e)}")
        return []


def fetch_kosis(stat_id: str, start_period: str) -> list:
    """KOSIS OpenAPI 호출"""
    from config import ECOS_KEY
    # KOSIS는 별도 키가 없으면 공개 API 사용 (PUBLIC_DATA_API_KEY 활용)
    import os
    kosis_key = os.getenv("KOSIS_API_KEY") or os.getenv("PUBLIC_DATA_API_KEY")
    url = "https://kosis.kr/openapi/Param/statisticsList.do"
    params = {
        "method": "getList",
        "apiKey": kosis_key,
        "statId": stat_id,
        "prdSe": "M",
        "startPrdDe": start_period,
        "format": "json",
        "jsonVD": "Y",
    }
    session = get_session()
    try:
        res = session.get(url, params=params, timeout=10)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        logger.error(f"[KOSIS] {stat_id} 수집 실패: {_sanitize_error(e)}")
        return []


def fetch_krx_index(market: str = "KOSPI") -> dict:
    """
    KRX 공식 데이터 포털에서 지수 수집
    market: 'KOSPI' or 'KOSDAQ'
    """
    url = "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "http://data.krx.co.kr",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload = {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT00101",
        "locale": "ko_KR",
        "mktId": "STK" if market == "KOSPI" else "KSQ",
        "share": "1",
        "money": "1",
        "csvxls_isNo": "false",
    }
    session = get_session()
    try:
        res = session.post(url, data=payload, headers=headers, timeout=10)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        logger.error(f"[KRX] {market} 수집 실패: {_sanitize_error(e)}")
        return {}


def fetch_fred(series_id: str, limit: int = 30, db_path: str = None) -> list:
    """FRED API 호출 (무료, 키 필요)"""
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit,
    }
    session = get_session()
    try:
        res = session.get(url, params=params, timeout=10)
        if res.status_code in (400, 401, 403):
            body = res.json() if res.text else {}
            msg = body.get("error_message", f"HTTP {res.status_code}")
            _record_auth_error("FRED", f"{series_id}: {msg}")
            return []
        res.raise_for_status()
        data = res.json()
        _save_raw(
            f"FRED:{series_id}",
            {
                "url": url,
                "params": params,
                "status_code": res.status_code,
                "response": data,
            },
            indicator=series_id,
            db_path=db_path,
        )
        # FRED는 API 키 오류 시 error_code 필드 포함
        if "error_code" in data:
            _record_auth_error("FRED", f"{series_id}: {data.get('error_message', data['error_code'])}")
            return []
        return data.get("observations", [])
    except Exception as e:
        logger.error(f"[FRED] {series_id} 수집 실패: {_sanitize_error(e)}")
        return []


def fetch_naver_news(query: str, display: int = 10) -> list:
    """Naver 뉴스 검색 API (당일 실시간, 무료)"""
    if not NAVER_ID or not NAVER_SECRET:
        logger.warning("[NAVER] NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET 미설정, 뉴스 수집 생략")
        return []
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_ID,
        "X-Naver-Client-Secret": NAVER_SECRET,
    }
    params = {
        "query": query,
        "display": display,
        "sort": "date",
    }
    session = get_session()
    try:
        res = session.get(url, headers=headers, params=params, timeout=10)
        if res.status_code in (401, 403):
            body = res.json() if res.text else {}
            err_msg = body.get("errorMessage", f"HTTP {res.status_code}")
            _record_auth_error("NAVER", f"{err_msg} (errorCode={body.get('errorCode','?')})")
            return []
        res.raise_for_status()
        return res.json().get("items", [])
    except Exception as e:
        logger.error(f"[NAVER] '{query}' 수집 실패: {_sanitize_error(e)}")
        return []


def fetch_rss(url: str) -> list:
    """RSS 파싱 (완전 무료, 인증 불필요)"""
    import feedparser
    try:
        feed = feedparser.parse(url)
        return feed.entries[:10]
    except Exception as e:
        logger.error(f"[RSS] {url} 파싱 실패: {_sanitize_error(e)}")
        return []


def fetch_kipris(keyword: str, page: int = 1) -> list:
    """KIPRIS 특허청 특허 검색 API"""
    if not KIPRIS_KEY:
        logger.warning("[KIPRIS] KIPRIS_API_KEY 미설정, 특허 수집 생략")
        return []
    url = "http://plus.kipris.or.kr/openapi/rest/PatentUtilityService/applicationNumberSearchInfo"
    params = {
        "accessToken": KIPRIS_KEY,
        "searchWord": keyword,
        "pageNo": page,
        "numOfRows": 10,
        "descSort": "true",
    }
    session = get_session()
    try:
        res = session.get(url, params=params, timeout=15)
        res.raise_for_status()
        # XML 응답 파싱
        import xml.etree.ElementTree as ET
        root = ET.fromstring(res.text)
        items = root.findall(".//item")
        return [{"title": item.findtext("inventionTitle", ""), "appNo": item.findtext("applicationNumber", "")} for item in items]
    except Exception as e:
        logger.error(f"[KIPRIS] '{keyword}' 수집 실패: {_sanitize_error(e)}")
        return []


# ── P2: 전력 병목 레이어 ─────────────────────────────────────────────────────

def fetch_ercot_grid_status(db_path: str = None) -> dict | None:
    """
    ERCOT (텍사스 전력망) 실시간 공개 데이터 수집
    - 현재 부하(MW), 공급 예비율(Reserve Margin %)
    출처: ERCOT Real-Time Grid Status (공개 JSON)
    반환: {"load_mw": float, "capacity_mw": float, "reserve_margin_pct": float, "timestamp": str}
    """
    url = "https://www.ercot.com/api/1/services/read/dashboards/supply-demand.json"
    session = get_session()
    try:
        res = session.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        res.raise_for_status()
        data = res.json()
        _save_raw(
            "ERCOT:supply-demand",
            {"url": url, "status_code": res.status_code, "response": data},
            db_path=db_path,
        )
        # ERCOT 대시보드 응답 파싱
        current = data.get("currentDemand", {})
        load_mw = current.get("demand")
        capacity_mw = current.get("capacity")
        if load_mw and capacity_mw and float(capacity_mw) > 0:
            reserve_margin_pct = round(
                (float(capacity_mw) - float(load_mw)) / float(capacity_mw) * 100, 2
            )
            result = {
                "load_mw": float(load_mw),
                "capacity_mw": float(capacity_mw),
                "reserve_margin_pct": reserve_margin_pct,
                "timestamp": data.get("lastUpdated", ""),
            }
            logger.info(f"[ERCOT] 부하={load_mw}MW, 예비율={reserve_margin_pct}%")
            return result
    except Exception as e:
        logger.warning(f"[ERCOT] 공식 endpoint 실패 - DCHub fallback 시도: {_sanitize_error(e)}")
    return fetch_grid_intelligence("ERCOT", db_path=db_path)


def fetch_pjm_load(db_path: str = None) -> dict | None:
    """
    PJM (미국 동부 전력망) 공개 데이터 수집
    - PJM 최신 실시간 부하(MW)
    출처: PJM Data Miner 2 공개 API
    반환: {"load_mw": float, "datetime_utc": str, "zone": "PJM"}
    """
    url = "https://api.pjm.com/api/v1/inst_load"
    params = {"fields": "datetime_beginning_utc,area_load", "sort": "datetime_beginning_utc desc", "rowCount": 1}
    session = get_session()
    try:
        public = _fetch_pjm_public_page(db_path=db_path)
        if public:
            return public
        res = session.get(
            url, params=params,
            headers={"Ocp-Apim-Subscription-Key": "", "User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        if res.status_code == 401:
            # PJM API는 구독키 필요 → 공개 대안: EIA API 사용
            return fetch_grid_intelligence("PJM", db_path=db_path)
        res.raise_for_status()
        items = res.json().get("items", [])
        if items:
            row = items[0]
            load_mw = float(row.get("area_load", 0))
            logger.info(f"[PJM] 부하={load_mw}MW")
            return {
                "load_mw": load_mw,
                "datetime_utc": row.get("datetime_beginning_utc", ""),
                "zone": "PJM",
            }
    except Exception as e:
        logger.warning(f"[PJM] Data Miner 수집 실패 - DCHub fallback 시도: {_sanitize_error(e)}")
    return fetch_grid_intelligence("PJM", db_path=db_path)


def _fetch_pjm_public_page(db_path: str = None) -> dict | None:
    """PJM 공개 Markets & Operations 페이지에서 current load를 파싱한다."""
    url = "https://www.pjm.com/markets-and-operations"
    session = get_session()
    try:
        res = session.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        res.raise_for_status()
        html = res.text
        _save_raw("PJM:markets-and-operations", {"url": url, "status_code": res.status_code, "html": html[:20000]}, db_path=db_path)
        match = re.search(r'<span class="currentloadico"></span><span><h2>([\d,]+)</h2></span>\s*current load \(MW\)', html)
        if not match:
            return None
        load_mw = float(match.group(1).replace(",", ""))
        time_match = re.search(r"Today's Outlook</h2>\s*As of ([^<]+)", html)
        timestamp = time_match.group(1).strip() if time_match else ""
        logger.info(f"[PJM public] 부하={load_mw:.0f}MW")
        return {"load_mw": load_mw, "datetime_utc": timestamp, "zone": "PJM", "source": "PJM:markets-and-operations"}
    except Exception as e:
        logger.warning(f"[PJM public] 페이지 파싱 실패: {_sanitize_error(e)}")
        return None


def fetch_grid_intelligence(region: str, db_path: str = None) -> dict | None:
    """
    ISO 공식 API가 WAF/API-key 문제로 막힐 때 쓰는 공개 EIA RTO 프록시 fallback.
    DCHub 응답의 note에 따르면 EIA hourly RTO 데이터를 사용한다.
    """
    url = f"https://dchub.cloud/api/v1/grid/intelligence/{region}"
    session = get_session()
    try:
        res = session.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        res.raise_for_status()
        data = res.json()
        _save_raw(f"DCHub:{region}", {"url": url, "status_code": res.status_code, "response": data}, db_path=db_path)
        load = data.get("demand_mw")
        if load is None:
            return None
        result = {
            "load_mw": float(str(load).replace(",", "")),
            "datetime_utc": data.get("demand_period", ""),
            "zone": region,
            "source": f"DCHub:{region}",
        }
        mix = data.get("generation_mix") or {}
        generation_mw = 0.0
        for item in mix.values():
            try:
                generation_mw += float(str(item.get("mw", 0)).replace(",", ""))
            except Exception:
                pass
        if generation_mw and result["load_mw"]:
            result["generation_mw"] = generation_mw
            result["reserve_margin_pct"] = round((generation_mw - result["load_mw"]) / result["load_mw"] * 100, 2)
        logger.info(f"[DCHub {region}] 부하={result['load_mw']:.0f}MW")
        return result
    except Exception as e:
        logger.warning(f"[DCHub {region}] fallback 실패: {_sanitize_error(e)}")
        return None


def _fetch_eia_power() -> dict | None:
    """
    EIA (미국 에너지청) 전력 수요 데이터 — PJM 대안
    FRED 시리즈 ELEC.CONS_TOT.RES.US.A 또는 EIA API
    """
    if not FRED_KEY:
        return None
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": "ELEC.GEN.ALL-US-99.M",
        "api_key": FRED_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 3,
    }
    session = get_session()
    try:
        res = session.get(url, params=params, timeout=10)
        res.raise_for_status()
        obs = res.json().get("observations", [])
        for o in obs:
            if o["value"] != ".":
                logger.info(f"[EIA via FRED] US 발전량: {o['date']} = {o['value']} GWh")
                return {"load_mw": None, "generation_gwh": float(o["value"]), "datetime_utc": o["date"], "zone": "US"}
    except Exception as e:
        logger.warning(f"[EIA] 수집 실패: {_sanitize_error(e)}")
    return None


def fetch_utility_capex(tickers: list[str] | None = None) -> list[dict]:
    """
    전력 유틸리티 기업 분기별 CapEx 수집 (FMP 사용)
    기본 대상: NEE(넥스트에라), DUK(듀크에너지), SO(서던컴퍼니)
    반환: [{"ticker": str, "date": str, "capex_b": float}, ...]
    """
    if tickers is None:
        tickers = ["NEE", "DUK", "SO"]
    results = []
    for ticker in tickers:
        data = fetch_fmp_capex(ticker, limit=4)
        results.extend(data)
    return results


# ── 한국투자증권 KIS OpenAPI ─────────────────────────────────────────────────

_KIS_BASE_REAL = "https://openapi.koreainvestment.com:9443"
_KIS_BASE_DEMO = "https://openapivts.koreainvestment.com:29443"
_kis_access_token: dict = {}   # 토큰 캐시 {token, expires_at}


def _kis_base() -> str:
    return _KIS_BASE_DEMO if KIS_ISDEMO else _KIS_BASE_REAL


def _get_kis_token() -> str | None:
    """KIS OAuth2 접근 토큰 발급 (캐시 유지)."""
    import time
    if not KIS_APP_KEY or not KIS_APP_SECRET:
        logger.warning("[KIS] KIS_APP_KEY / KIS_APP_SECRET 설정 안 됨")
        return None
    now = time.time()
    if _kis_access_token.get("token") and _kis_access_token.get("expires_at", 0) > now + 60:
        return _kis_access_token["token"]
    try:
        res = requests.post(
            f"{_kis_base()}/oauth2/tokenP",
            json={"grant_type": "client_credentials", "appkey": KIS_APP_KEY, "appsecret": KIS_APP_SECRET},
            timeout=10,
        )
        res.raise_for_status()
        data = res.json()
        token = data.get("access_token")
        if not token:
            logger.error(f"[KIS] 토큰 발급 실패: {data.get('msg1', 'unknown')}")
            return None
        expires_in = int(data.get("expires_in", 86400))
        _kis_access_token["token"] = token
        _kis_access_token["expires_at"] = now + expires_in
        logger.info("[KIS] 액세스 토큰 발급 완료")
        return token
    except Exception as e:
        logger.error(f"[KIS] 토큰 요청 오류: {_sanitize_error(e)}")
        _record_auth_error("KIS", str(e))
        return None


def fetch_kis_ohlcv(
    symbol: str,
    period: str = "D",
    count: int = 100,
    db_path: str = DEFAULT_DB_PATH,
) -> list[dict]:
    """
    KIS OpenAPI로 국내 상장 주식·지수 일별 OHLCV 조회.
    period: "D"=일, "W"=주, "M"=월
    반환: [{"date": "YYYY-MM-DD", "open": float, "high": float, "low": float,
             "close": float, "volume": int}, ...] 최신순
    """
    token = _get_kis_token()
    if not token:
        return []

    from datetime import date
    today = date.today().strftime("%Y%m%d")
    start = "19900101"  # 충분히 과거로 설정 (count로 제한)

    tr_id = "FHKST01010400"  # 국내 주식 기간별 시세
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": KIS_APP_KEY,
        "appsecret": KIS_APP_SECRET,
        "tr_id": tr_id,
        "custtype": "P",
    }
    params = {
        "fid_cond_mrkt_div_code": "J",
        "fid_input_iscd": symbol,
        "fid_input_date_1": start,
        "fid_input_date_2": today,
        "fid_period_div_code": period,
        "fid_org_adj_prc": "0",  # 수정주가 미사용
    }
    url = f"{_kis_base()}/uapi/domestic-stock/v1/quotations/inquire-daily-price"
    try:
        res = get_session().get(url, headers=headers, params=params, timeout=10)
        if res.status_code in (401, 403):
            _record_auth_error("KIS", f"HTTP {res.status_code}: {res.text[:200]}")
            return []
        res.raise_for_status()
        items = res.json().get("output", [])
        if not items:
            logger.warning(f"[KIS] {symbol} OHLCV 데이터 없음")
            return []
        results = []
        for item in items[:count]:
            try:
                results.append({
                    "date":   item["stck_bsop_date"][:4] + "-" + item["stck_bsop_date"][4:6] + "-" + item["stck_bsop_date"][6:],
                    "open":   float(item["stck_oprc"]),
                    "high":   float(item["stck_hgpr"]),
                    "low":    float(item["stck_lwpr"]),
                    "close":  float(item["stck_clpr"]),
                    "volume": int(item["acml_vol"]),
                })
            except (KeyError, ValueError):
                continue
        logger.info(f"[KIS] {symbol} OHLCV {len(results)}건 수집")
        return results
    except Exception as e:
        logger.error(f"[KIS] {symbol} 조회 오류: {_sanitize_error(e)}")
        return []
