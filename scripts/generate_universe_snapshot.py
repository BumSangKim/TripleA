from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.universe.loader import load_asset_master, load_asset_schema, load_universe_selectors
from api.universe.snapshot import build_universe_snapshot, write_universe_snapshot
from api.universe.validator import validate_asset_master, validate_selectors


def main() -> None:
    asset_master = load_asset_master()
    schema = load_asset_schema()
    selectors = load_universe_selectors()

    validate_asset_master(asset_master, schema)
    validate_selectors(selectors)

    as_of_date = asset_master["as_of_date"]
    snapshot = build_universe_snapshot(
        asset_master=asset_master,
        selectors=selectors,
        as_of_date=as_of_date,
    )
    output_path = Path("config/universe/snapshots") / f"{snapshot['snapshot_id']}.yml"
    write_universe_snapshot(snapshot, output_path)
    print(output_path)


if __name__ == "__main__":
    main()
