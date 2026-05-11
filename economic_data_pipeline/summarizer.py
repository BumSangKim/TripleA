# summarizer.py
# 수집된 지표의 통계 요약 산출
from database import get_latest
from preprocessor import clean_series, compute_stats

INDICATORS = {
    "CPI":          {"label": "소비자물가지수",          "unit": "pt(2020=100)"},
    "PPI":          {"label": "생산자물가지수",          "unit": "pt(2020=100)"},
    "USD_KRW":      {"label": "원/달러 환율",            "unit": "원"},
    "BASE_RATE":    {"label": "한국 기준금리",           "unit": "%"},
    "KOSPI":        {"label": "코스피",                  "unit": "pt"},
    "KOSDAQ":       {"label": "코스닥",                  "unit": "pt"},
    "UNEMPLOYMENT": {"label": "실업률",                  "unit": "%"},
    "DUBAI_OIL":    {"label": "두바이유",                "unit": "USD/bbl"},
    "GOLD":         {"label": "금 가격",                 "unit": "USD/oz"},
    "WTI":          {"label": "WTI 국제유가",            "unit": "USD/bbl"},
    "US_CPI":       {"label": "미국 CPI",                "unit": "index"},
    "FED_RATE":     {"label": "미국 기준금리",           "unit": "%"},
    "BOND_3Y":      {"label": "국고채(3년)",             "unit": "%"},
    "GDP_GROWTH":   {"label": "경제성장률(전기比)",      "unit": "%"},
    "PMI_SDT":      {"label": "공급망압력(GSCPI·PMI)", "unit": "σ"},
    "US10Y":        {"label": "미국 10Y 국채금리",       "unit": "%"},
    "USD_INDEX":    {"label": "달러무역가중지수(DTWEXBGS)", "unit": "index"},
    "DXY":          {"label": "달러인덱스(DXY·ICE)",    "unit": "index"},
}

# Hyperscaler CapEx 지표 (FMP - Deep Research S1)
CAPEX_TICKERS = {
    "CAPEX_MSFT":  {"label": "Microsoft CapEx",  "unit": "B USD"},
    "CAPEX_GOOGL": {"label": "Alphabet CapEx",   "unit": "B USD"},
    "CAPEX_META":  {"label": "Meta CapEx",        "unit": "B USD"},
    "CAPEX_AMZN":  {"label": "Amazon CapEx",      "unit": "B USD"},
}


def build_summary(db_path: str = "economic_data.db") -> dict:
    """모든 지표의 최신 통계 산출"""
    result = {}
    for key, meta in INDICATORS.items():
        df = get_latest(key, n=30, db_path=db_path)
        if df.empty:
            result[key] = {**meta, "error": "데이터 없음"}
            continue
        df = clean_series(df)
        stats = compute_stats(df)
        result[key] = {**meta, **stats}
    return result


def build_capex_summary(db_path: str = "economic_data.db") -> dict:
    """Hyperscaler CapEx 분기별 요약 산출 (최근 5분기)"""
    import sqlite3
    result = {}
    conn = sqlite3.connect(db_path)
    for key, meta in CAPEX_TICKERS.items():
        rows = conn.execute(
            "SELECT date, value FROM indicators WHERE indicator=? ORDER BY date DESC LIMIT 5",
            (key,),
        ).fetchall()
        if not rows:
            result[key] = {**meta, "quarters": [], "error": "데이터 없음"}
            continue
        quarters = [{"date": r[0], "capex_b": r[1]} for r in rows]
        latest = quarters[0]["capex_b"]
        prev   = quarters[1]["capex_b"] if len(quarters) > 1 else None
        yoy    = quarters[4]["capex_b"] if len(quarters) >= 5 else None
        result[key] = {
            **meta,
            "quarters": quarters,
            "latest": latest,
            "latest_date": quarters[0]["date"],
            "qoq_pct": round((latest / prev - 1) * 100, 1) if prev else None,
            "yoy_pct": round((latest / yoy - 1) * 100, 1) if yoy else None,
        }
    conn.close()
    return result
