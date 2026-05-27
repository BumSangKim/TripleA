from api.universe.loader import load_assets, load_universe_selectors


BLOCKED_RISK_TAGS = {
    "leveraged",
    "inverse",
    "futures_direct",
    "options_direct",
    "crypto_direct",
}


def test_stocks_are_not_order_candidates():
    offenders = [
        asset["asset_id"]
        for asset in load_assets()
        if asset["asset_type"] == "STOCK" and asset["tradability"]["order_candidate"] is not False
    ]

    assert not offenders


def test_assets_are_not_enabled_for_order_candidate_before_backtest():
    offenders = [
        asset["asset_id"]
        for asset in load_assets()
        if asset["tradability"]["enabled_state"] == "enabled_for_order_candidate_after_approval"
    ]

    assert not offenders


def test_asset_master_has_no_blocked_risk_tags():
    offenders = []
    for asset in load_assets():
        blocked = sorted(set(asset.get("risk_tags") or []) & BLOCKED_RISK_TAGS)
        if blocked:
            offenders.append(f"{asset['asset_id']}: {blocked}")

    assert not offenders, "\n".join(offenders)


def test_selectors_do_not_use_asset_id_buckets():
    selectors = load_universe_selectors()["selectors"]

    assert not _contains_key(selectors, "asset_ids")


def _contains_key(value, target: str) -> bool:
    if isinstance(value, dict):
        return target in value or any(_contains_key(item, target) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, target) for item in value)
    return False
