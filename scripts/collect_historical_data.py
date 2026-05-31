#!/usr/bin/env python3
"""
Collect historical market data through the canonical service collector.

Usage:
    PYTHONPATH=. python scripts/collect_historical_data.py --start 2021-01-01 --end 2026-05-25
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect historical market data into TripleA DB")
    parser.add_argument("--start", default="2010-01-01", help="Start date YYYY-MM-DD (default: 2010-01-01)")
    parser.add_argument("--end", default=date.today().isoformat(), help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--dry-run", action="store_true", help="List assets but do not fetch or write data")
    args = parser.parse_args()

    try:
        start = _parse_date(args.start)
        end = _parse_date(args.end)
    except ValueError as exc:
        print(f"[ERROR] Invalid date: {exc}", file=sys.stderr)
        sys.exit(1)
    if start > end:
        print("[ERROR] --start must be earlier than or equal to --end", file=sys.stderr)
        sys.exit(1)

    from api.db.connection import DB_PATH
    from api.db.initialize import initialize_database
    from api.market_data_collector import collect_for_asset_codes
    from api.market_data_service import get_asset_universe

    initialize_database()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        asset_codes = [
            asset.asset_code
            for asset in get_asset_universe(conn, active_only=True)
            if asset.source_type != "manual"
        ]
        if args.dry_run:
            print(f"Dry run: {len(asset_codes)} assets would be collected")
            for asset_code in sorted(asset_codes):
                print(f"  [{asset_code}]")
            return
        print(f"Collecting {len(asset_codes)} assets: {start.isoformat()} -> {end.isoformat()}")
        results = collect_for_asset_codes(conn, asset_codes, start, end)
    finally:
        conn.close()

    saved = sum(results.values())
    for key, count in sorted(results.items()):
        print(f"  [{key}] {count} rows")
    print(f"\nDone. Total rows saved: {saved}")


if __name__ == "__main__":
    main()
