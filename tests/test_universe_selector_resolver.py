import pytest

from api.universe.loader import load_assets, load_universe_selectors
from api.universe.selector import (
    UniverseSelectorError,
    asset_matches_selector,
    resolve_all_selectors,
    resolve_selector,
)


def _selectors():
    return load_universe_selectors()["selectors"]


def test_initial_order_candidate_universe_returns_etfs_only():
    resolved = resolve_all_selectors(load_assets(), _selectors())

    initial = resolved["initial_order_candidate_universe"]

    assert initial
    assert {asset["asset_type"] for asset in initial} == {"ETF"}


def test_initial_order_candidate_universe_returns_no_stocks():
    resolved = resolve_all_selectors(load_assets(), _selectors())

    initial = resolved["initial_order_candidate_universe"]

    assert all(asset["asset_type"] != "STOCK" for asset in initial)


def test_semiconductor_order_candidates_returns_semiconductor_etfs():
    resolved = resolve_all_selectors(load_assets(), _selectors())

    semiconductor = resolved["semiconductor_order_candidates"]

    assert semiconductor
    assert all(asset["asset_type"] == "ETF" for asset in semiconductor)
    assert all("semiconductor_exposure" in asset["features"] for asset in semiconductor)


def test_semiconductor_scoring_references_can_include_etfs_and_stocks():
    resolved = resolve_all_selectors(load_assets(), _selectors())

    references = resolved["semiconductor_scoring_references"]

    assert references
    assert {"ETF", "STOCK"}.issubset({asset["asset_type"] for asset in references})


def test_blocked_risk_tag_excluded():
    selector = _selectors()["semiconductor_scoring_references"]
    blocked_asset = {
        "asset_id": "BLOCKED",
        "asset_type": "STOCK",
        "features": ["semiconductor_exposure"],
        "risk_tags": ["blocked_product"],
        "tradability": {"order_candidate": False, "enabled_state": "monitor_only"},
    }

    assert not asset_matches_selector(blocked_asset, selector)


def test_unknown_selector_syntax_raises_explicit_exception():
    with pytest.raises(UniverseSelectorError):
        resolve_selector(
            load_assets(),
            {"include": {"features": {"none": ["leveraged"]}}, "exclude": {}},
        )


def test_selector_result_has_no_duplicate_asset_ids():
    assets = load_assets()
    duplicated_assets = assets + [assets[0]]

    resolved = resolve_selector(
        duplicated_assets,
        _selectors()["initial_order_candidate_universe"],
    )
    asset_ids = [asset["asset_id"] for asset in resolved]

    assert len(asset_ids) == len(set(asset_ids))
