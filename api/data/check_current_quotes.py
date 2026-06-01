from __future__ import annotations

import argparse
from pathlib import Path

from api.data.ingestion import check_current_quotes
from api.data.providers import MockMarketDataProvider
from api.data.source_registry import load_data_sources


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check current quote connectivity using read-only providers.")
    parser.add_argument("--source-id", default="mock_current_quotes")
    parser.add_argument("--provider", default="mock")
    parser.add_argument("--output", default="data/PHASE_3_CURRENT_PRICE_CHECK.md")
    args = parser.parse_args(argv)

    source = next(source for source in load_data_sources() if source.source_id == args.source_id)
    provider = MockMarketDataProvider()
    result = check_current_quotes(source=source, provider=provider)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "\n".join(
            [
                "# Phase 3 Current Price Check",
                "",
                f"- source_id: `{result.source_id}`",
                f"- provider: `{args.provider}`",
                f"- status: `{result.status}`",
                f"- row_count: `{result.row_count}`",
                f"- warnings: `{', '.join(result.warnings) if result.warnings else 'none'}`",
                "- live_check: `skipped unless RUN_LIVE_PRICE_SMOKE=1 is explicitly set`",
                "- execution: no broker order, balance, or order-permission path is used",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"{result.status} {result.row_count}")
    return 0 if result.status in {"success", "empty"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
