# summarizer.py
# 수집된 지표의 통계 요약 산출
from database import get_latest
from preprocessor import clean_series, compute_stats

INDICATORS = {
    "CPI":          {"label": "소비자물가지수",   "unit": "%"},
    "PPI":          {"label": "생산자물가지수",   "unit": "%"},
    "USD_KRW":      {"label": "원/달러 환율",     "unit": "원"},
    "BASE_RATE":    {"label": "기준금리",          "unit": "%"},
    "KOSPI":        {"label": "코스피",            "unit": "pt"},
    "UNEMPLOYMENT": {"label": "실업률",            "unit": "%"},
    "DUBAI_OIL":    {"label": "두바이유",          "unit": "USD/bbl"},
    "WTI":          {"label": "WTI 국제유가",      "unit": "USD/bbl"},
    "GOLD":         {"label": "금 가격",           "unit": "USD/oz"},
    "US_CPI":       {"label": "미국 CPI",          "unit": "%"},
    "FED_RATE":     {"label": "미국 기준금리",     "unit": "%"},
    "GSCPI":        {"label": "공급망 압력지수",   "unit": ""},
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
