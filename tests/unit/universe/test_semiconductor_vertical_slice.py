from __future__ import annotations

import copy

import pytest

from api.universe.loader import load_asset_master, load_yaml
from api.universe.semiconductor import (
    SEMICONDUCTOR_SUBSECTORS,
    SemiconductorUniverseError,
    load_semiconductor_vertical_slice,
    parse_semiconductor_vertical_slice,
)


def _config():
    return load_yaml("config/universe/semiconductor_vertical_slice.yml")


def _asset_master():
    return load_asset_master("config/universe")


def test_semiconductor_vertical_slice_loads_deterministically():
    first = load_semiconductor_vertical_slice()
    second = load_semiconductor_vertical_slice()

    assert first == second
    assert {item.subsector_id for item in first.subsectors} == SEMICONDUCTOR_SUBSECTORS
    assert first.benchmark.benchmark_id == "MSCI_WORLD"
    assert first.benchmark.role == "core_benchmark"
    assert first.benchmark.tradeable is False
    assert first.active_overlay.role == "active_overlay"


def test_candidate_identity_references_asset_master_without_display_name_or_ticker_copy():
    config = _config()
    serialized = str(config)
    universe = load_semiconductor_vertical_slice()

    assert "symbol" not in serialized
    assert "name" not in serialized
    assert set(universe.candidate_asset_ids).issubset(
        {asset["asset_id"] for asset in _asset_master()["assets"]}
    )


def test_duplicate_candidate_asset_id_fails_conservatively():
    config = copy.deepcopy(_config())
    config["subsectors"][1]["candidate_asset_ids"] = ["KRX_005930"]

    with pytest.raises(SemiconductorUniverseError, match="duplicate candidate asset_id"):
        parse_semiconductor_vertical_slice(config, asset_master=_asset_master())


def test_unknown_subsector_fails_conservatively():
    config = copy.deepcopy(_config())
    config["subsectors"][0]["subsector_id"] = "unapproved_subsector"

    with pytest.raises(SemiconductorUniverseError, match="unknown subsector"):
        parse_semiconductor_vertical_slice(config, asset_master=_asset_master())


def test_missing_core_benchmark_role_fails_conservatively():
    config = copy.deepcopy(_config())
    config["benchmark"]["role"] = "active_overlay"

    with pytest.raises(SemiconductorUniverseError, match="benchmark.role"):
        parse_semiconductor_vertical_slice(config, asset_master=_asset_master())


def test_invalid_candidate_asset_type_fails_conservatively():
    master = copy.deepcopy(_asset_master())
    asset = next(asset for asset in master["assets"] if asset["asset_id"] == "KRX_396500")
    asset["asset_type"] = "INDEX"

    with pytest.raises(SemiconductorUniverseError, match="invalid asset type"):
        parse_semiconductor_vertical_slice(_config(), asset_master=master)
