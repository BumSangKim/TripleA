#!/usr/bin/env python3
"""
Send the current TripleA macro report to Telegram.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.db.connection import get_conn
from api.db.initialize import initialize_database
from api.macro_telegram_report import send_daily_macro_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Send the daily macro Telegram report.")
    parser.add_argument("--force", action="store_true", help="Send even if today's report was already sent.")
    parser.add_argument("--dry-run", action="store_true", help="Build the report without sending it.")
    args = parser.parse_args()

    initialize_database()
    with get_conn() as conn:
        result = send_daily_macro_report(conn, force=args.force, dry_run=args.dry_run)

    print(
        "ok={ok} sent={sent} skipped={skipped} indicators={count} message={message}".format(
            ok=str(result.ok).lower(),
            sent=result.sent,
            skipped=result.skipped,
            count=result.indicator_count,
            message=result.message,
        )
    )
    if args.dry_run and result.text:
        print("")
        print(result.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
