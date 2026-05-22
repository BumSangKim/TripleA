"""
scripts/fetch_history.py
6개월 히스토리 데이터 수집 스크립트

사용법:
    cd /Users/bumsangkim/Dev/TripleA
    python scripts/fetch_history.py

의존성: yfinance, fredapi (선택)
    pip install yfinance
    pip install fredapi  # FRED 데이터 필요 시
"""
from __future__ import annotations
import sqlite3
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

# 프로젝트 루트를 sys.path에 추가
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "data" / "economic_data.db"
load_dotenv(ROOT / ".env")

# Yahoo Finance 티커 → (indicator_key, unit)
YAHOO_SYMBOLS = {
    "^KS11":    ("KOSPI",  "pt"),
    "^KQ11":    ("KOSDAQ", "pt"),
    "SPY":      ("SPY",    "USD"),
    "QQQ":      ("QQQ",    "USD"),
    "GC=F":     ("GOLD",   "USD"),
    "CL=F":     ("WTI",    "USD"),
    "BZ=F":     ("BRENT",  "USD"),
    "DX-Y.NYB": ("DXY",    "pt"),
    "^TNX":     ("US10Y",  "%"),
    "SMH":      ("SMH",    "USD"),
    "SOXX":     ("SOXX",   "USD"),
    "XLU":      ("XLU",    "USD"),
    "MSFT":     ("MSFT",   "USD"),
    "GOOGL":    ("GOOGL",  "USD"),
    "META":     ("META",   "USD"),
    "AMZN":     ("AMZN",   "USD"),
    "NVDA":     ("NVDA",   "USD"),
}

# FRED 시리즈 → (indicator_key, unit)
FRED_SERIES = {
    "CPIAUCSL": ("CPI",          "%"),
    "FEDFUNDS": ("FED_RATE",     "%"),
    "DGS10":    ("US10Y_FRED",   "%"),
    "UNRATE":   ("UNEMPLOYMENT", "%"),
    "DTWEXBGS": ("DXY_FRED",     "pt"),
    "DCOILWTICO": ("WTI_FRED",   "USD"),
}


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_api_key(name: str) -> str:
    """환경변수/.env를 우선 사용하고, 없으면 API_KEY 파일을 읽는다."""
    env_value = os.getenv(name, "").strip()
    if env_value:
        return env_value

    key_path = ROOT / "API_KEY" / name
    if key_path.exists():
        return key_path.read_text().strip()
    return ""


def upsert(conn: sqlite3.Connection, key: str, value: float, unit: str, date_str: str, source: str):
    conn.execute("""
        INSERT INTO indicators (indicator, value, unit, date, source)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(date, indicator) DO UPDATE SET value=excluded.value, source=excluded.source
    """, (key, round(float(value), 4), unit, date_str, source))


def fetch_yahoo(period: str = "6mo") -> int:
    """Yahoo Finance에서 6개월 일봉 데이터 수집"""
    try:
        import yfinance as yf
    except ImportError:
        print("[WARN] yfinance 미설치. `pip install yfinance` 후 재실행")
        return 0

    tickers = list(YAHOO_SYMBOLS.keys())
    print(f"[Yahoo] {len(tickers)}개 티커 {period} 수집 중...")
    try:
        data = yf.download(tickers, period=period, interval="1d", progress=True, auto_adjust=True)
    except Exception as e:
        print(f"[Yahoo] 다운로드 오류: {e}")
        return 0

    close = data["Close"] if "Close" in data else data
    count = 0
    with get_db() as conn:
        for ticker, (key, unit) in YAHOO_SYMBOLS.items():
            col = ticker if ticker in close.columns else None
            if col is None:
                print(f"  [SKIP] {ticker} 컬럼 없음")
                continue
            series = close[col].dropna()
            for dt_idx, val in series.items():
                if hasattr(dt_idx, "strftime"):
                    date_str = dt_idx.strftime("%Y-%m-%d")
                else:
                    date_str = str(dt_idx)[:10]
                try:
                    upsert(conn, key, float(val), unit, date_str, "Yahoo")
                    count += 1
                except (ValueError, TypeError):
                    continue
        conn.commit()
    print(f"[Yahoo] {count}건 저장 완료")
    return count


def fetch_fred(period_days: int = 180) -> int:
    """FRED API에서 6개월 데이터 수집"""
    api_key = get_api_key("FRED_API_KEY")
    if not api_key:
        print("[WARN] FRED_API_KEY 설정 없음, FRED 수집 건너뜀")
        return 0

    try:
        from fredapi import Fred
    except ImportError:
        print("[WARN] fredapi 미설치. `pip install fredapi` 후 재실행")
        return 0

    fred = Fred(api_key=api_key)
    start = (datetime.today() - timedelta(days=period_days)).strftime("%Y-%m-%d")
    count = 0
    with get_db() as conn:
        for series_id, (key, unit) in FRED_SERIES.items():
            try:
                s = fred.get_series(series_id, observation_start=start)
                for dt_idx, val in s.items():
                    if val != val:  # NaN check
                        continue
                    if hasattr(dt_idx, "strftime"):
                        date_str = dt_idx.strftime("%Y-%m-%d")
                    else:
                        date_str = str(dt_idx)[:10]
                    try:
                        upsert(conn, key, float(val), unit, date_str, f"FRED:{series_id}")
                        count += 1
                    except (ValueError, TypeError):
                        continue
                print(f"  [FRED] {series_id} → {key}: {len(s.dropna())}건")
            except Exception as e:
                print(f"  [FRED] {series_id} 오류: {e}")
        conn.commit()
    print(f"[FRED] {count}건 저장 완료")
    return count


def fetch_ecos(period_days: int = 180) -> int:
    """ECOS (한국은행) API에서 주요 지표 수집"""
    api_key = get_api_key("ECOS_API_KEY")
    if not api_key:
        print("[WARN] ECOS_API_KEY 설정 없음, ECOS 수집 건너뜀")
        return 0

    import urllib.request
    import json

    start = (datetime.today() - timedelta(days=period_days)).strftime("%Y%m")
    end = datetime.today().strftime("%Y%m")

    # 한국은행 기준금리 (기준금리 통계: 731Y001, 0101000)
    # ECOS API는 월별/분기별이 대부분
    ecos_items = [
        # (stat_code, item_code, key, unit, freq)
        ("731Y001", "0101000", "BASE_RATE", "%", "M"),  # 기준금리 (월)
        ("036Y001", "0000001", "USD_KRW",   "원", "M"),  # 원달러환율
    ]

    count = 0
    with get_db() as conn:
        for stat_code, item_code, key, unit, freq in ecos_items:
            url = (
                f"https://ecos.bok.or.kr/api/StatisticSearch/{api_key}/json/kr/1/1000/"
                f"{stat_code}/{freq}/{start}/{end}/{item_code}"
            )
            try:
                with urllib.request.urlopen(url, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                rows = data.get("StatisticSearch", {}).get("row", [])
                for row in rows:
                    date_str_raw = row.get("TIME", "")
                    val_str = row.get("DATA_VALUE", "")
                    if not date_str_raw or not val_str:
                        continue
                    # YYYYMM → YYYY-MM-01
                    if len(date_str_raw) == 6:
                        date_str = f"{date_str_raw[:4]}-{date_str_raw[4:6]}-01"
                    elif len(date_str_raw) == 8:
                        date_str = f"{date_str_raw[:4]}-{date_str_raw[4:6]}-{date_str_raw[6:8]}"
                    else:
                        continue
                    try:
                        upsert(conn, key, float(val_str.replace(",", "")), unit, date_str, "ECOS")
                        count += 1
                    except (ValueError, TypeError):
                        continue
                print(f"  [ECOS] {stat_code}/{item_code} → {key}: {len(rows)}건")
            except Exception as e:
                print(f"  [ECOS] {stat_code} 오류: {e}")
        conn.commit()
    print(f"[ECOS] {count}건 저장 완료")
    return count


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="6개월 히스토리 데이터 수집")
    parser.add_argument("--source", choices=["all", "yahoo", "fred", "ecos"], default="all")
    parser.add_argument("--period", default="6mo", help="Yahoo Finance period (e.g. 6mo, 1y)")
    parser.add_argument("--days", type=int, default=180, help="FRED/ECOS 수집 기간(일)")
    args = parser.parse_args()

    total = 0
    if args.source in ("all", "yahoo"):
        total += fetch_yahoo(args.period)
    if args.source in ("all", "fred"):
        total += fetch_fred(args.days)
    if args.source in ("all", "ecos"):
        total += fetch_ecos(args.days)
    print(f"\n[완료] 총 {total}건 수집/업데이트")
