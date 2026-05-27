import copy

import pytest

from api.universe.loader import (
    load_asset_master,
    load_asset_schema,
    load_assets,
    load_universe_selectors,
)
from api.universe.validator import (
    AssetMasterValidationError,
    validate_asset_master,
    validate_selectors,
)


def _master():
    return load_asset_master("config/universe")


def _schema():
    return load_asset_schema("config/universe")


def test_schema_yml_loads():
    assert load_asset_schema("config/universe")["version"].startswith("asset_master_schema")


def test_asset_master_yml_loads():
    assert load_assets("config/universe")


def test_universe_selectors_yml_loads():
    assert load_universe_selectors("config/universe")["selectors"]


def test_asset_master_validation_passes():
    validate_asset_master(_master(), _schema())


def test_duplicate_asset_id_fails():
    master = copy.deepcopy(_master())
    master["assets"].append(copy.deepcopy(master["assets"][0]))

    with pytest.raises(AssetMasterValidationError, match="duplicate asset_id"):
        validate_asset_master(master, _schema())


def test_duplicate_market_symbol_fails():
    master = copy.deepcopy(_master())
    duplicate = copy.deepcopy(master["assets"][1])
    duplicate["asset_id"] = "DUPLICATE_ASSET"
    duplicate["market"] = master["assets"][0]["market"]
    duplicate["symbol"] = master["assets"][0]["symbol"]
    master["assets"].append(duplicate)

    with pytest.raises(AssetMasterValidationError, match="duplicate market/symbol"):
        validate_asset_master(master, _schema())


def test_stock_order_candidate_true_fails():
    master = copy.deepcopy(_master())
    stock = next(asset for asset in master["assets"] if asset["asset_type"] == "STOCK")
    stock["tradability"]["order_candidate"] = True

    with pytest.raises(AssetMasterValidationError, match="stock cannot be order candidate"):
        validate_asset_master(master, _schema())


def test_blocked_risk_tag_fails():
    master = copy.deepcopy(_master())
    master["assets"][0]["risk_tags"].append("leveraged")

    with pytest.raises(AssetMasterValidationError, match="blocked risk tag"):
        validate_asset_master(master, _schema())


def test_selector_asset_ids_bucket_fails():
    selectors = copy.deepcopy(load_universe_selectors("config/universe"))
    selectors["selectors"]["bad"] = {"include": {"asset_ids": ["KRX_360750"]}}

    with pytest.raises(AssetMasterValidationError, match="asset_ids"):
        validate_selectors(selectors)
