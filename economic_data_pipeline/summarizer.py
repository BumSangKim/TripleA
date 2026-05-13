# summarizer.py
# 수집된 지표의 통계 요약 산출
# 지표 메타데이터는 config/indicators.yaml에서 로드 (단일 출처)
from pathlib import Path

import yaml

from database import get_latest
from preprocessor import clean_series, compute_stats

_YAML_PATH = Path(__file__).parent / "config" / "indicators.yaml"


def _load_yaml() -> dict:
    try:
        with open(_YAML_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return {}


def _get_indicators_by_layer(*layers: str) -> dict:
    """지정 레이어의 지표 {key: meta} 딕셔너리 반환"""
    data = _load_yaml()
    all_inds = data.get("indicators", {})
    if not layers:
        return all_inds
    return {k: v for k, v in all_inds.items() if v.get("layer") in layers}


# ── 하위 호환 상수 (기존 코드가 import하는 경우 대비) ──────────────────────────
def _build_indicators_dict() -> dict:
    data = _load_yaml()
    return {
        k: {"label": v.get("label", k), "unit": v.get("unit", "")}
        for k, v in data.get("indicators", {}).items()
        if not k.startswith("CAPEX_") and v.get("layer") not in ("equity",)
    }

def _build_capex_dict() -> dict:
    data = _load_yaml()
    return {
        k: {"label": v.get("label", k), "unit": v.get("unit", "B USD")}
        for k, v in data.get("indicators", {}).items()
        if k.startswith("CAPEX_")
    }

# 기존 코드와 호환 유지
INDICATORS = _build_indicators_dict()
CAPEX_TICKERS = _build_capex_dict()


def build_summary(db_path: str = "economic_data.db") -> dict:
    """
    핵심 매크로 지표(CapEx·ETF 제외)의 최신 통계 산출.
    지표 목록은 indicators.yaml의 macro·korea·commodity·us·supply_chain 레이어.
    """
    layers = ("macro", "korea", "commodity", "us", "supply_chain")
    indicators = _get_indicators_by_layer(*layers)

    result = {}
    for key, meta in indicators.items():
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
    capex_inds = _get_indicators_by_layer("ai_bottleneck")
    result = {}
    conn = sqlite3.connect(db_path)
    for key, meta in capex_inds.items():
        if not key.startswith("CAPEX_"):
            continue
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


def build_equity_summary(db_path: str = "economic_data.db") -> dict:
    """P2: 섹터 ETF 및 상대강도 요약"""
    equity_inds = _get_indicators_by_layer("equity", "power")
    result = {}
    for key, meta in equity_inds.items():
        df = get_latest(key, n=30, db_path=db_path)
        if df.empty:
            result[key] = {**meta, "error": "데이터 없음"}
            continue
        df = clean_series(df)
        result[key] = {**meta, **compute_stats(df)}
    return result

