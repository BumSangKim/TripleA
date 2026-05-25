"""
api/macro_indicator_collector.py
On-demand collection for macro indicator history.
"""
from __future__ import annotations

import logging
import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("uvicorn.error")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDICATORS_YAML = PROJECT_ROOT / "config" / "indicators.yaml"
API_KEY_DIR = PROJECT_ROOT / "API_KEY"


def load_indicator_catalog() -> dict[str, dict[str, Any]]:
    if not INDICATORS_YAML.exists():
        return {}
    data = yaml.safe_load(INDICATORS_YAML.read_text(encoding="utf-8")) or {}
    return data.get("indicators") or {}


def get_indicator_meta(indicator: str) -> dict[str, Any] | None:
    return load_indicator_catalog().get(indicator)


def collect_indicator_history(
    conn: sqlite3.Connection,
    indicator: str,
    start: date,
    end: date,
) -> int:
    """Collect an indicator's history into the indicators table when supported."""
    if start > end:
        return 0

    meta = get_indicator_meta(indicator)
    if not meta:
        logger.info("[macro_collector] %s has no indicator metadata; skipped", indicator)
        return 0

    source_type = (meta.get("source_type") or "").strip()
    if source_type == "yahoo_quote":
        return _collect_yahoo_indicator(conn, indicator, meta, start, end)
    if source_type == "fred":
        return _collect_fred_indicator(conn, indicator, meta, start, end)
    if source_type == "hybrid_market_fred":
        count = _collect_fred_indicator(conn, indicator, {**meta, "symbol": meta.get("fred_symbol")}, start, end)
        return count or _collect_yahoo_indicator(conn, indicator, meta, start, end)
    if source_type == "fmp_capex":
        return _collect_fmp_capex(conn, indicator, meta, start, end)

    logger.info("[macro_collector] %s source_type=%r is not on-demand supported", indicator, source_type)
    return 0


def _collect_yahoo_indicator(
    conn: sqlite3.Connection,
    indicator: str,
    meta: dict[str, Any],
    start: date,
    end: date,
) -> int:
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("[macro_collector] yfinance not installed; skipping %s", indicator)
        return 0

    symbol = meta.get("symbol")
    if not symbol:
        return 0

    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(), auto_adjust=True)
    except Exception as exc:
        logger.warning("[macro_collector] yfinance error for %s (%s): %s", indicator, symbol, exc)
        return 0
    if df is None or df.empty:
        logger.info("[macro_collector] no Yahoo rows for %s (%s)", indicator, symbol)
        return 0

    rows = []
    for idx, row in df.iterrows():
        value_date = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        close = row.get("Close")
        if close is None or close != close:
            continue
        rows.append((value_date, indicator, float(close), f"Yahoo:{symbol}", meta.get("unit")))
    return _upsert_indicator_rows(conn, rows)


def _collect_fred_indicator(
    conn: sqlite3.Connection,
    indicator: str,
    meta: dict[str, Any],
    start: date,
    end: date,
) -> int:
    api_key = _read_secret("FRED_API_KEY")
    symbol = meta.get("symbol")
    if not api_key or not symbol:
        return 0

    try:
        from fredapi import Fred
    except ImportError:
        logger.warning("[macro_collector] fredapi not installed; skipping %s", indicator)
        return 0

    try:
        fred = Fred(api_key=api_key)
        series = fred.get_series(symbol, observation_start=start.isoformat(), observation_end=end.isoformat())
    except Exception as exc:
        logger.warning("[macro_collector] FRED error for %s (%s): %s", indicator, symbol, exc)
        return 0
    if series is None or series.empty:
        logger.info("[macro_collector] no FRED rows for %s (%s)", indicator, symbol)
        return 0

    rows = []
    for idx, value in series.items():
        if value != value:
            continue
        value_date = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        rows.append((value_date, indicator, float(value), f"FRED:{symbol}", meta.get("unit")))
    return _upsert_indicator_rows(conn, rows)


def _collect_fmp_capex(
    conn: sqlite3.Connection,
    indicator: str,
    meta: dict[str, Any],
    start: date,
    end: date,
) -> int:
    api_key = _read_secret("FMP_API_KEY", aliases=("FINANCIAL_MODELING_PREP_KEY",))
    symbol = meta.get("symbol")
    if not api_key or not symbol:
        return 0

    try:
        import requests
    except ImportError:
        logger.warning("[macro_collector] requests not installed; skipping %s", indicator)
        return 0

    period_count = max(8, min(120, int((end - start).days / 90) + 8))
    url = f"https://financialmodelingprep.com/api/v3/cash-flow-statement/{symbol}"
    try:
        response = requests.get(
            url,
            params={"period": "quarter", "limit": period_count, "apikey": api_key},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        logger.warning("[macro_collector] FMP error for %s (%s): %s", indicator, symbol, _mask_secret(str(exc), api_key))
        return 0
    if not isinstance(payload, list):
        return 0

    rows = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        raw_date = str(item.get("date") or "")[:10]
        try:
            value_date = date.fromisoformat(raw_date)
        except ValueError:
            continue
        if value_date < start or value_date > end:
            continue
        capex = item.get("capitalExpenditure")
        if capex is None:
            continue
        try:
            value = round(abs(float(capex)) / 1_000_000_000, 3)
        except (TypeError, ValueError):
            continue
        rows.append((value_date.isoformat(), indicator, value, f"FMP:{symbol}", meta.get("unit") or "B USD"))
    return _upsert_indicator_rows(conn, rows)


def _upsert_indicator_rows(conn: sqlite3.Connection, rows: list[tuple[str, str, float, str, str | None]]) -> int:
    if not rows:
        return 0
    conn.executemany(
        """
        INSERT OR REPLACE INTO indicators
        (date, indicator, value, source, unit, updated)
        VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def _read_secret(name: str, aliases: tuple[str, ...] = ()) -> str | None:
    for key in (name, *aliases):
        value = os.getenv(key)
        if value:
            return value.strip()
        path = API_KEY_DIR / key
        if path.exists():
            raw = path.read_text(encoding="utf-8").strip()
            value = raw.split("=", 1)[-1].strip() if "=" in raw else raw
            if value:
                return value
    return None


def _mask_secret(message: str, secret: str | None) -> str:
    if not secret:
        return message
    return message.replace(secret, "***")
