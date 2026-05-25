"""
api/market_data_collector.py
자산 코드 목록을 받아 Yahoo Finance / FRED 에서 데이터를 수집해 DB에 저장한다.
외부 네트워크 접근이 필요하므로, 백테스트 엔진 내부가 아닌 서비스 레이어에서만 호출해야 한다.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger("uvicorn.error")

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_symbol_map_from_yaml() -> dict[str, dict[str, Any]]:
    """investment_universe.yaml 에서 asset_code → {symbol, currency, source_type} 매핑을 반환."""
    import yaml

    path = PROJECT_ROOT / "config" / "investment_universe.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    result: dict[str, dict[str, Any]] = {}
    for universe in (data.get("universes") or {}).values():
        for asset in (universe.get("assets") or []):
            code = asset.get("asset_code")
            if code:
                result[code] = {
                    "symbol": asset.get("symbol", code),
                    "currency": asset.get("currency", "KRW"),
                    "source_type": asset.get("source_type", "yahoo"),
                    "name": asset.get("name"),
                    "asset_class": asset.get("asset_class"),
                    "market": asset.get("market"),
                }
    return result


def _ensure_asset_in_universe(conn: sqlite3.Connection, asset_code: str, meta: dict[str, Any]) -> None:
    """asset_universe 테이블에 해당 코드가 없으면 삽입한다."""
    existing = conn.execute(
        "SELECT asset_code FROM asset_universe WHERE asset_code=?", (asset_code,)
    ).fetchone()
    if existing:
        return
    conn.execute(
        """
        INSERT INTO asset_universe
        (asset_code, symbol, name, asset_class, market, currency, source_type, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
            asset_code,
            meta["symbol"],
            meta.get("name"),
            meta.get("asset_class"),
            meta.get("market"),
            meta["currency"],
            meta["source_type"],
        ),
    )
    conn.commit()
    logger.info("[collector] registered %s → asset_universe", asset_code)


def _collect_yahoo(
    conn: sqlite3.Connection,
    symbol: str,
    asset_code: str,
    currency: str,
    start: date,
    end: date,
) -> int:
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("[collector] yfinance not installed; skipping %s", asset_code)
        return 0

    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start.isoformat(), end=end.isoformat(), auto_adjust=True)
    except Exception as exc:
        logger.warning("[collector] yfinance error for %s (%s): %s", asset_code, symbol, exc)
        return 0
    if df is None or df.empty:
        logger.warning("[collector] No Yahoo data for %s (%s)", asset_code, symbol)
        return 0

    rows = []
    for idx, row in df.iterrows():
        price_date = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        close = row.get("Close")
        if close is None or close != close:  # NaN check
            continue
        adj_close = float(close)
        rows.append((asset_code, price_date, adj_close, adj_close, currency, "yahoo"))

    if rows:
        conn.executemany(
            """
            INSERT OR REPLACE INTO market_prices
            (asset_code, price_date, close, adj_close, currency, source)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    logger.info("[collector] %s: %d rows saved", asset_code, len(rows))
    return len(rows)


def _collect_usdkrw_fred(conn: sqlite3.Connection, start: date, end: date) -> int:
    """FRED DEXKOUS 시리즈로 USD/KRW 환율 수집. 실패 시 0 반환."""
    key_path = PROJECT_ROOT / "API_KEY" / "FRED_API_KEY"
    if not key_path.exists():
        logger.warning("[collector] FRED_API_KEY not found; skipping USD/KRW FRED fetch")
        return _collect_usdkrw_yahoo(conn, start, end)

    raw = key_path.read_text().strip()
    api_key = raw.split("=", 1)[-1].strip() if "=" in raw else raw
    if not api_key:
        return _collect_usdkrw_yahoo(conn, start, end)

    try:
        from fredapi import Fred

        fred = Fred(api_key=api_key)
        series = fred.get_series("DEXKOUS", observation_start=start.isoformat(), observation_end=end.isoformat())
        if series is None or series.empty:
            return _collect_usdkrw_yahoo(conn, start, end)

        rows = []
        for idx, value in series.items():
            if value != value:
                continue
            rate_date = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
            rows.append(("USD", "KRW", rate_date, float(value), "fred"))

        if rows:
            conn.executemany(
                """
                INSERT OR REPLACE INTO fx_rates
                (base_currency, quote_currency, rate_date, rate, source)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
        logger.info("[collector] USD/KRW FRED: %d rows saved", len(rows))
        return len(rows)
    except Exception as exc:
        logger.warning("[collector] FRED failed (%s); falling back to Yahoo", exc)
        return _collect_usdkrw_yahoo(conn, start, end)


def _collect_usdkrw_yahoo(conn: sqlite3.Connection, start: date, end: date) -> int:
    """Yahoo Finance USDKRW=X 로 USD/KRW 환율 수집. FRED 실패 시 폴백."""
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("[collector] yfinance not installed; skipping USD/KRW Yahoo fetch")
        return 0

    ticker = yf.Ticker("USDKRW=X")
    df = ticker.history(start=start.isoformat(), end=end.isoformat(), auto_adjust=True)
    if df is None or df.empty:
        logger.warning("[collector] No Yahoo data for USDKRW=X")
        return 0

    rows = []
    for idx, row in df.iterrows():
        rate_date = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        close = row.get("Close")
        if close is None or close != close:
            continue
        rows.append(("USD", "KRW", rate_date, float(close), "yahoo"))

    if rows:
        conn.executemany(
            """
            INSERT OR REPLACE INTO fx_rates
            (base_currency, quote_currency, rate_date, rate, source)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    logger.info("[collector] USD/KRW Yahoo: %d rows saved", len(rows))
    return len(rows)


def collect_for_asset_codes(
    conn: sqlite3.Connection,
    asset_codes: list[str],
    start: date,
    end: date,
) -> dict[str, int]:
    """
    주어진 자산 코드 목록에 대해 start~end 범위의 시장 데이터를 수집한다.
    asset_universe 에 없는 코드는 investment_universe.yaml 에서 보완한다.
    반환값: {asset_code: 저장된 행 수}
    """
    from .market_data_service import get_asset_universe

    # DB asset_universe 로드
    db_universe = {item.asset_code: item for item in get_asset_universe(conn, active_only=False)}
    # YAML 폴백 로드
    yaml_map = _load_symbol_map_from_yaml()

    results: dict[str, int] = {}
    needs_usd_fx = False

    for code in asset_codes:
        asset = db_universe.get(code)

        # asset_universe 에 없으면 YAML 에서 보완
        if asset is None:
            meta = yaml_map.get(code)
            if meta is None:
                logger.warning("[collector] %s not found in asset_universe or investment_universe.yaml; skipped", code)
                results[code] = 0
                continue
            _ensure_asset_in_universe(conn, code, meta)
            # 재로드
            db_universe = {item.asset_code: item for item in get_asset_universe(conn, active_only=False)}
            asset = db_universe.get(code)
            if asset is None:
                results[code] = 0
                continue

        if asset.source_type == "manual":
            results[code] = 0
            continue

        if asset.source_type != "yahoo":
            logger.warning("[collector] %s has unsupported source_type=%r; skipped", code, asset.source_type)
            results[code] = 0
            continue

        n = _collect_yahoo(conn, asset.symbol, code, asset.currency, start, end)
        results[code] = n

        if asset.currency == "USD":
            needs_usd_fx = True

    if needs_usd_fx:
        results["USD/KRW"] = _collect_usdkrw_fred(conn, start, end)

    return results
