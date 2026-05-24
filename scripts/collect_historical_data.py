#!/usr/bin/env python3
"""
scripts/collect_historical_data.py
Yahoo Finance와 FRED에서 시장 데이터를 수집해 DB에 저장한다.

사용법:
    python scripts/collect_historical_data.py [--start 2010-01-01] [--end 2024-12-31] [--dry-run]

의존 패키지:
    pip install yfinance fredapi
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _get_conn() -> sqlite3.Connection:
    from api.db import DB_PATH, ensure_dashboard_tables
    ensure_dashboard_tables()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _collect_yahoo(
    conn: sqlite3.Connection,
    symbol: str,
    asset_code: str,
    currency: str,
    start: str,
    end: str,
    *,
    dry_run: bool = False,
) -> int:
    try:
        import yfinance as yf
    except ImportError:
        print("  [SKIP] yfinance not installed. Run: pip install yfinance")
        return 0

    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start, end=end, auto_adjust=True)
    if df.empty:
        print(f"  [WARN] No data returned for {symbol}")
        return 0

    rows = []
    for idx, row in df.iterrows():
        price_date = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        adj_close = float(row["Close"]) if "Close" in row and row["Close"] == row["Close"] else None
        if adj_close is None:
            continue
        rows.append((asset_code, price_date, adj_close, adj_close, currency, "yahoo"))

    if not dry_run and rows:
        conn.executemany(
            """
            INSERT OR REPLACE INTO market_prices
            (asset_code, price_date, close, adj_close, currency, source)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    return len(rows)


def _collect_fred_usdkrw(
    conn: sqlite3.Connection,
    start: str,
    end: str,
    *,
    dry_run: bool = False,
) -> int:
    """FRED DEXKOUS 시리즈로 USD/KRW 환율 수집."""
    fred_key_path = PROJECT_ROOT / "API_KEY" / "FRED_API_KEY"
    if not fred_key_path.exists():
        print("  [SKIP] API_KEY/FRED_API_KEY not found")
        return 0

    raw = fred_key_path.read_text().strip()
    # 파일이 'KEY=<value>' 형식일 경우 값만 추출
    api_key = raw.split("=", 1)[-1].strip() if "=" in raw else raw
    if not api_key:
        print("  [SKIP] FRED_API_KEY is empty")
        return 0

    try:
        from fredapi import Fred
    except ImportError:
        print("  [SKIP] fredapi not installed. Run: pip install fredapi")
        return 0

    try:
        fred = Fred(api_key=api_key)
        series = fred.get_series("DEXKOUS", observation_start=start, observation_end=end)
    except Exception as exc:
        print(f"  [WARN] FRED request failed: {exc}")
        return 0

    if series is None or series.empty:
        print("  [WARN] No FRED DEXKOUS data returned")
        return 0

    rows = []
    for idx, value in series.items():
        if value != value:  # NaN check
            continue
        rate_date = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        rows.append(("USD", "KRW", rate_date, float(value), "fred"))

    if not dry_run and rows:
        conn.executemany(
            """
            INSERT OR REPLACE INTO fx_rates
            (base_currency, quote_currency, rate_date, rate, source)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect historical market data into TripleA DB")
    parser.add_argument("--start", default="2010-01-01", help="Start date YYYY-MM-DD (default: 2010-01-01)")
    parser.add_argument("--end", default=date.today().isoformat(), help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--dry-run", action="store_true", help="Fetch data but do not write to DB")
    args = parser.parse_args()

    try:
        datetime.strptime(args.start, "%Y-%m-%d")
        datetime.strptime(args.end, "%Y-%m-%d")
    except ValueError as e:
        print(f"[ERROR] Invalid date: {e}")
        sys.exit(1)

    print(f"Collecting market data: {args.start} → {args.end}"
          + (" [DRY RUN]" if args.dry_run else ""))

    from api.market_data_service import get_asset_universe

    conn = _get_conn()
    universe = get_asset_universe(conn, active_only=True)

    total_prices = 0
    for asset in universe:
        if asset.source_type == "manual":
            print(f"  [{asset.asset_code}] manual asset — skipped")
            continue
        if asset.source_type != "yahoo":
            print(f"  [{asset.asset_code}] unsupported source_type={asset.source_type!r} — skipped")
            continue

        print(f"  [{asset.asset_code}] {asset.symbol} ({asset.currency}) via Yahoo Finance...")
        n = _collect_yahoo(conn, asset.symbol, asset.asset_code, asset.currency, args.start, args.end, dry_run=args.dry_run)
        print(f"    → {n} rows {'(dry run)' if args.dry_run else 'saved'}")
        total_prices += n

    print("  [USD/KRW] via FRED DEXKOUS...")
    n_fx = _collect_fred_usdkrw(conn, args.start, args.end, dry_run=args.dry_run)
    print(f"    → {n_fx} rows {'(dry run)' if args.dry_run else 'saved'}")

    conn.close()
    print(f"\nDone. Prices: {total_prices}, FX rows: {n_fx}")

    if args.dry_run:
        print("(Dry run: nothing was written to the DB)")


if __name__ == "__main__":
    main()
