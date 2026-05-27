import yaml

from api.universe.loader import load_asset_master, load_universe_selectors
from api.universe.snapshot import build_universe_snapshot, write_universe_snapshot


def test_build_universe_snapshot_contains_versions_and_resolved_selectors():
    asset_master = load_asset_master()
    selectors = load_universe_selectors()

    snapshot = build_universe_snapshot(
        asset_master=asset_master,
        selectors=selectors,
        as_of_date=asset_master["as_of_date"],
    )

    assert snapshot["snapshot_id"] == "universe_snapshot_20260527"
    assert snapshot["asset_master_version"] == "asset_master_v0.1"
    assert snapshot["selector_version"] == "universe_selectors_v0.1"
    assert snapshot["as_of_date"] == "2026-05-27"
    assert snapshot["resolved"]["initial_order_candidate_universe"]


def test_snapshot_resolved_assets_include_minimum_fields_only():
    snapshot = build_universe_snapshot(
        asset_master=load_asset_master(),
        selectors=load_universe_selectors(),
        as_of_date="2026-05-27",
    )

    asset = snapshot["resolved"]["initial_order_candidate_universe"][0]

    assert set(asset) == {"asset_id", "symbol", "market", "name", "asset_type"}


def test_write_universe_snapshot_round_trips_yaml(tmp_path):
    snapshot = build_universe_snapshot(
        asset_master=load_asset_master(),
        selectors=load_universe_selectors(),
        as_of_date="2026-05-27",
    )
    output_path = tmp_path / "universe_snapshot_20260527.yml"

    write_universe_snapshot(snapshot, output_path)

    loaded = yaml.safe_load(output_path.read_text(encoding="utf-8"))
    assert loaded == snapshot
