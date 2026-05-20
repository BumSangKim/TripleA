# ir_scraper.py
# SEC EDGAR에서 Hyperscaler + AI 반도체 병목 기업 IR 자료 스크래핑
# 대상: MSFT/AMZN/META/GOOGL (AI CapEx) + NVDA/MU + TSMC(20-F) + 삼성/SK하이닉스(뉴스 키워드)
import requests
import time
import logging
from bs4 import BeautifulSoup
from storage.database import DB_PATH

logger = logging.getLogger(__name__)

# ── AI 병목 레이어 기업 CIK 매핑 ─────────────────────────────────────────────
COMPANY_CIKS = {
    # Hyperscaler (AI CapEx S1)
    "MSFT":  "0000789019",
    "AMZN":  "0001018724",
    "META":  "0001326801",
    "GOOGL": "0001652044",
    # AI 반도체 병목 (S2/S3)
    "NVDA":  "0001045810",   # NVIDIA — GPU 수요 지표
    "MU":    "0000723125",   # Micron — HBM 수급
    "TSMC":  "0001046179",   # TSMC (20-F, 연간 보고서도 포함)
    "AMD":   "0000002488",   # AMD
    "AVGO":  "0001730168",   # Broadcom
    "SMCI":  "0001375365",   # Super Micro Computer
    "DELL":  "0001571996",   # Dell Technologies
    "INTC":  "0000050863",   # Intel
}
COMPANY_NAMES = {
    "MSFT":  "마이크로소프트",
    "AMZN":  "아마존",
    "META":  "메타",
    "GOOGL": "구글(알파벳)",
    "NVDA":  "NVIDIA",
    "MU":    "마이크론",
    "TSMC":  "TSMC",
    "AMD":   "AMD",
    "AVGO":  "Broadcom",
    "SMCI":  "Super Micro Computer",
    "DELL":  "Dell Technologies",
    "INTC":  "인텔",
}

# AI 병목 관련 키워드 (요약 시 중요도 강조용)
AI_BOTTLENECK_KEYWORDS = [
    "data center", "datacenter", "ai infrastructure", "gpu", "HBM", "high bandwidth memory",
    "capital expenditure", "capex", "hyperscaler", "inference", "training",
    "supply constraint", "demand", "backlog", "compute",
    "lead time", "allocation", "supply constrained", "tight supply", "HBM3E", "CoWoS",
    "advanced packaging",
]

# SEC EDGAR 요구 User-Agent
HEADERS = {
    "User-Agent": "TripleA Pipeline bumsangkim@dev.io",
    "Accept-Encoding": "gzip, deflate",
}

MAX_TEXT_CHARS = 8000   # Gemini 토큰 절약을 위한 텍스트 제한


def count_ai_bottleneck_keywords(text: str) -> dict[str, int]:
    """AI 병목 키워드 등장 횟수 카운트."""
    import re

    if not text:
        return {keyword: 0 for keyword in AI_BOTTLENECK_KEYWORDS}
    counts = {}
    for keyword in AI_BOTTLENECK_KEYWORDS:
        pattern = re.compile(rf"\b{re.escape(keyword)}\b", re.IGNORECASE)
        counts[keyword] = len(pattern.findall(text))
    return counts


def fetch_recent_8k(ticker: str, limit: int = 5) -> list[dict]:
    """
    SEC EDGAR에서 특정 기업의 최근 8-K(또는 20-F) 파일링 목록 반환.
    TSMC는 20-F(연간)도 포함.
    Returns: [{"accession": str, "date": str, "form": str, "doc": str,
               "ticker": str, "company": str, "cik": str}]
    """
    cik = COMPANY_CIKS.get(ticker)
    if not cik:
        logger.warning(f"[IR] 알 수 없는 ticker: {ticker}")
        return []

    # TSMC는 20-F 연간 보고서도 포함
    target_forms = {"8-K", "8-K/A", "20-F"} if ticker == "TSMC" else {"8-K", "8-K/A"}

    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.error(f"[IR] EDGAR 조회 실패 ({ticker}): {e}")
        return []

    recent = data.get("filings", {}).get("recent", {})
    forms  = recent.get("form", [])
    dates  = recent.get("filingDate", [])
    accns  = recent.get("accessionNumber", [])
    pdocs  = recent.get("primaryDocument", [])

    filings = []
    for i, form in enumerate(forms):
        if form in target_forms and len(filings) < limit:
            filings.append({
                "accession": accns[i],
                "date":      dates[i],
                "form":      form,
                "doc":       pdocs[i],
                "ticker":    ticker,
                "company":   COMPANY_NAMES.get(ticker, ticker),
                "cik":       cik,
            })

    logger.info(f"[IR] {ticker} {'/'.join(target_forms)} {len(filings)}건 조회")
    return filings


def fetch_filing_text(accession: str, cik: str, primary_doc: str) -> str:
    """
    SEC EDGAR에서 파일링 문서 다운로드 후 텍스트 추출.
    우선순위: Exhibit 99.1 (실적 보도자료) > 첫 번째 HTML > primary_doc
    최대 MAX_TEXT_CHARS 글자 반환
    """
    acc_clean = accession.replace("-", "")
    cik_int = int(cik)
    base_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/"

    best_doc = primary_doc

    # 인덱스 페이지에서 Exhibit 99.1 (보도자료) 탐색
    try:
        index_url = f"{base_url}{accession}-index.htm"
        r_idx = requests.get(index_url, headers=HEADERS, timeout=15)
        if r_idx.status_code == 200:
            soup_idx = BeautifulSoup(r_idx.content, "html.parser")
            exhibit99 = None
            first_html = None

            for row in soup_idx.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 3:
                    continue
                # 파일명
                link_tag = cells[2].find("a") if len(cells) > 2 else None
                if not link_tag:
                    continue
                href = link_tag.get("href", "")
                fname = href.split("/")[-1]

                # 문서 타입 (4번째 셀)
                doc_type = cells[3].get_text(strip=True) if len(cells) > 3 else ""

                if fname.endswith((".htm", ".html")):
                    # XBRL/R숫자 파일 제외
                    if any(x in fname.lower() for x in ["_htm.xml", "xbrl"]):
                        continue
                    if first_html is None:
                        first_html = fname
                    # Exhibit 99.1 = 실적 보도자료
                    if "EX-99" in doc_type.upper() or "99.1" in doc_type:
                        exhibit99 = fname

            if exhibit99:
                best_doc = exhibit99
                logger.info(f"[IR] Exhibit 99.1 발견: {exhibit99}")
            elif first_html and first_html != primary_doc:
                best_doc = first_html
                logger.info(f"[IR] 첫 번째 HTML 선택: {first_html}")
    except Exception as e:
        logger.warning(f"[IR] 인덱스 파싱 실패 ({accession}): {e}")

    # 문서 다운로드 및 텍스트 추출
    doc_url = f"{base_url}{best_doc}"
    try:
        r = requests.get(doc_url, headers=HEADERS, timeout=20)
        r.raise_for_status()

        soup = BeautifulSoup(r.content, "html.parser")

        for tag in soup(["script", "style", "head", "meta", "link", "noscript", "ix:header"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = "\n".join(lines)

        logger.info(f"[IR] 텍스트 추출 완료: {best_doc} ({len(text)}자)")
        return text[:MAX_TEXT_CHARS]

    except Exception as e:
        logger.error(f"[IR] 문서 다운로드 실패 ({accession}, {best_doc}): {e}")
        return ""


def get_new_filings(
    db_path: str = DB_PATH,
    tickers: list[str] | None = None,
) -> list[dict]:
    """
    DB에 없는 신규 파일링만 반환.
    tickers 미지정 시 모든 COMPANY_CIKS 대상.
    AI 병목 신호 강화를 위해 NVDA/MU/TSMC/AMD/INTC 포함.
    """
    import sqlite3

    conn = sqlite3.connect(db_path)
    seen = set(
        row[0] for row in
        conn.execute("SELECT accession FROM ir_filings").fetchall()
    )
    conn.close()

    scan_tickers = tickers or list(COMPANY_CIKS.keys())
    new_filings = []
    for ticker in scan_tickers:
        filings = fetch_recent_8k(ticker, limit=5)
        for f in filings:
            if f["accession"] not in seen:
                logger.info(f"[IR] 신규 파일링 발견: {ticker} {f['date']} {f['accession']}")
                new_filings.append(f)
        time.sleep(0.5)   # SEC EDGAR rate limit 준수

    return new_filings
