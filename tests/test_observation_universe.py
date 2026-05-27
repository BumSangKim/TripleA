from api.observation_universe import load_observation_universe, load_scoreflow_sector_taxonomy
from api.strategy_config import load_investment_universe


def test_observation_universe_separates_observation_and_investable_flags():
    universe = load_observation_universe()
    asset = universe["assets"][0]
    assert "observation_enabled" in asset
    assert "investable_enabled" in asset
    assert "sector_codes" in asset


def test_existing_investment_universe_still_loads():
    assert load_investment_universe("default_global")["assets"]


def test_sector_taxonomy_has_plugin_metadata():
    taxonomy = load_scoreflow_sector_taxonomy()
    assert "SEMICONDUCTOR" in taxonomy
    assert "specialized_plugins" in taxonomy["SEMICONDUCTOR"]
