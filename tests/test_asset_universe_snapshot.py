import json

from api.asset_universe_snapshot import export_asset_universe_snapshot


FIXED_CREATED_AT = "2026-05-26T00:00:00+00:00"


def test_snapshot_export_succeeds_for_valid_config():
    snapshot = export_asset_universe_snapshot(created_at=FIXED_CREATED_AT)

    assert snapshot["snapshot_id"]
    assert snapshot["created_at"] == FIXED_CREATED_AT
    assert snapshot["asset_count_total"] >= 6
    assert snapshot["validation"]["is_valid"] is True
    assert snapshot["assets"]


def test_same_input_produces_stable_snapshot_id():
    first = export_asset_universe_snapshot(created_at="2026-05-26T00:00:00+00:00")
    second = export_asset_universe_snapshot(created_at="2026-05-27T00:00:00+00:00")

    assert first["snapshot_id"] == second["snapshot_id"]


def test_disabled_watchlist_assets_are_included_but_non_actionable():
    snapshot = export_asset_universe_snapshot(created_at=FIXED_CREATED_AT)
    watchlist = next(asset for asset in snapshot["assets"] if asset["asset_id"] == "ROBOT_WATCHLIST")

    assert watchlist["enabled"] is False
    assert watchlist["role"] == "watchlist"
    assert watchlist["eligible_for_order_candidate"] is False
    assert snapshot["asset_count_watchlist"] >= 1


def test_validation_result_is_included():
    snapshot = export_asset_universe_snapshot(created_at=FIXED_CREATED_AT)

    assert {"is_valid", "errors", "warnings", "review_required_assets", "active_asset_count"}.issubset(
        snapshot["validation"]
    )


def test_malformed_config_does_not_produce_actionable_snapshot(tmp_path):
    malformed = tmp_path / "asset_universe.yaml"
    malformed.write_text("assets: [", encoding="utf-8")

    snapshot = export_asset_universe_snapshot(malformed, created_at=FIXED_CREATED_AT)

    assert snapshot["asset_count_enabled"] == 0
    assert snapshot["assets"] == []
    assert snapshot["validation"]["is_valid"] is False
    assert snapshot["validation"]["conservative_state"] == "REVIEW_REQUIRED"


def test_snapshot_can_be_written_to_json_file(tmp_path):
    output = tmp_path / "snapshot.json"
    snapshot = export_asset_universe_snapshot(created_at=FIXED_CREATED_AT, output_path=output)

    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["snapshot_id"] == snapshot["snapshot_id"]
