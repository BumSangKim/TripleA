# collector.py
# 각 데이터 소스에서 경제 지표를 수집하는 모듈
# ECOS StatisticSearch 대신 KeyStatisticList 사용 (더 안정적)
import requests
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from config import ECOS_KEY, FRED_KEY, FMP_KEY, NAVER_ID, NAVER_SECRET, KIPRIS_KEY

logger = logging.getLogger(__name__)


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


def fetch_ecos_keystat() -> dict:
    """
    ECOS KeyStatisticList API 호출 - 한국은행 핵심 경제지표 전체 조회
    StatisticSearch보다 안정적이며 CPI, PPI, 환율, 금리, 코스피, 실업률, 두바이유, 금 등 포함
    반환: {지표명: {'value': float, 'unit': str}}
    """
    url = f"https://ecos.bok.or.kr/api/KeyStatisticList/{ECOS_KEY}/json/kr/1/200/"
    session = get_session()
    try:
        res = session.get(url, timeout=10)
        res.raise_for_status()
        rows = res.json().get("KeyStatisticList", {}).get("row", [])
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
        logger.error(f"[ECOS KeyStatisticList] 수집 실패: {e}")
        return {}


def fetch_dxy_yahoo() -> float | None:
    """
    Yahoo Finance에서 실제 DXY (ICE US Dollar Index, DX-Y.NYB) 수집
    DTWEXBGS(달러 무역가중지수)와 구별되는 ICE 기준 달러인덱스
    반환: 최신 종가 (float) 또는 None
    """
    val = fetch_yahoo_quote("DX-Y.NYB")
    return val[1] if val else None


def fetch_yahoo_quote(symbol: str) -> tuple[str, float] | None:
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
        result = res.json().get("chart", {}).get("result", [{}])[0]
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
        logger.error(f"[Yahoo {symbol}] 수집 실패: {e}")
        return None


def fetch_fmp_capex(ticker: str, limit: int = 5) -> list[dict]:
    """
    Financial Modeling Prep API - 분기별 CapEx 수집
    Hyperscaler AI CapEx 신호 (Deep Research S1): MSFT, GOOGL, META, AMZN
    반환: [{"date": "2026-03-31", "capex_b": 30.88, "ticker": "MSFT"}, ...]
           capex_b는 십억 달러(Billion USD) 기준 (양수)
    limit: 최대 5 (FMP 무료 플랜 제한)
    """
    if not FMP_KEY:
        logger.warning("[FMP] FMP_API_KEY 미설정 - CapEx 수집 건너뜀")
        return []
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
        res.raise_for_status()
        if not res.text:
            logger.warning(f"[FMP] {ticker} 빈 응답")
            return []
        data = res.json()
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
        logger.error(f"[FMP] {ticker} 수집 실패: {e}")
        return []


def fetch_nyfed_pmi_sdt() -> float | None:
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
                logger.info(f"[NY Fed GSCPI] 최신값: {date_str} = {val:.4f}")
                return float(val)
        logger.warning("[NY Fed GSCPI] 유효 데이터 행 없음")
        return None
    except Exception as e:
        logger.error(f"[NY Fed GSCPI] 수집 실패: {e}")
        return None



    """
    한국은행 ECOS API 호출
    freq: 'DD'(일), 'MM'(월), 'QQ'(분기)
    """
    url = (
        f"https://ecos.bok.or.kr/api/StatisticSearch/{ECOS_KEY}"
        f"/json/kr/1/100/{stat_id}/{freq}/{start}/{end}/"
    )
    session = get_session()
    try:
        res = session.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        rows = data.get("StatisticSearch", {}).get("row", [])
        return rows
    except Exception as e:
        logger.error(f"[ECOS] {stat_id} 수집 실패: {e}")
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
        logger.error(f"[KOSIS] {stat_id} 수집 실패: {e}")
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
        logger.error(f"[KRX] {market} 수집 실패: {e}")
        return {}


def fetch_fred(series_id: str, limit: int = 30) -> list:
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
        res.raise_for_status()
        return res.json().get("observations", [])
    except Exception as e:
        logger.error(f"[FRED] {series_id} 수집 실패: {e}")
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
        res.raise_for_status()
        return res.json().get("items", [])
    except Exception as e:
        logger.error(f"[NAVER] '{query}' 수집 실패: {e}")
        return []


def fetch_rss(url: str) -> list:
    """RSS 파싱 (완전 무료, 인증 불필요)"""
    import feedparser
    try:
        feed = feedparser.parse(url)
        return feed.entries[:10]
    except Exception as e:
        logger.error(f"[RSS] {url} 파싱 실패: {e}")
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
        logger.error(f"[KIPRIS] '{keyword}' 수집 실패: {e}")
        return []
