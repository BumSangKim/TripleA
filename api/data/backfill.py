from __future__ import annotations

import argparse
import sqlite3
from datetime import date

from api.db import connection as api_db
from api.data.ingestion import IngestionResult, collect_macro_data, collect_price_history
from api.data.providers import FailingProvider, MockMacroDataProvider, MockMarketDataProvider
from api.data.repository import count_rows, ensure_raw_data_tables
from api.data.source_registry import load_data_sources


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Idempotent Phase 3 data backfill.")
    parser.add_argument("--dataset", choices=["prices", "macro"], required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--provider", default="mock", choices=["mock", "failing"])
    parser.add_argument("--source-id")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args(argv)

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if start > end:
        raise SystemExit("start must be before or equal to end")

    sources = load_data_sources()
    source_type = "market_price" if args.dataset == "prices" else "macro"
    candidates = [source for source in sources if source.source_type == source_type]
    if args.source_id:
        candidates = [source for source in candidates if source.source_id == args.source_id]
    candidates = [source for source in candidates if source.enabled]
    if not candidates:
        raise SystemExit(f"no enabled source for dataset={args.dataset}")

    if args.dry_run:
        print(f"dry_run dataset={args.dataset} sources={','.join(source.source_id for source in candidates)}")
        return 0

    provider = _provider(args.dataset, args.provider)
    with api_db.get_conn() as conn:
        results = [
            _run_source(conn, source=source, dataset=args.dataset, start=start, end=end, provider=provider)
            for source in candidates
        ]
    for result in results:
        print(f"{result.source_id} {result.status} rows={result.row_count}")
        if args.fail_fast and result.status == "failed":
            return 1
    return 0 if all(result.status != "failed" for result in results) else 1


def run_backfill_for_test(
    *,
    conn: sqlite3.Connection,
    dataset: str,
    start: date,
    end: date,
    source_id: str | None = None,
    provider=None,
    dry_run: bool = False,
) -> list[IngestionResult]:
    if start > end:
        raise ValueError("start must be before or equal to end")
    sources = load_data_sources()
    source_type = "market_price" if dataset == "prices" else "macro"
    candidates = [source for source in sources if source.source_type == source_type and source.enabled]
    if source_id:
        candidates = [source for source in candidates if source.source_id == source_id]
    if dry_run:
        ensure_raw_data_tables(conn)
        return [IngestionResult(source.source_id, "dry_run", 0, []) for source in candidates]
    return [
        _run_source(conn, source=source, dataset=dataset, start=start, end=end, provider=provider or _provider(dataset, "mock"))
        for source in candidates
    ]


def _run_source(conn, *, source, dataset: str, start: date, end: date, provider) -> IngestionResult:
    if dataset == "prices":
        return collect_price_history(source=source, start_date=start, end_date=end, provider=provider, db_session=conn)
    return collect_macro_data(source=source, start_date=start, end_date=end, provider=provider, db_session=conn)


def _provider(dataset: str, provider_name: str):
    if provider_name == "failing":
        return FailingProvider()
    if dataset == "macro":
        return MockMacroDataProvider()
    return MockMarketDataProvider()


if __name__ == "__main__":
    raise SystemExit(main())
