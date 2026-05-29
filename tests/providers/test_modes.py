import pytest

from api.providers.modes import (
    MODE_POLICIES,
    ModePolicy,
    TradingMode,
    get_mode_policy,
    normalize_mode,
)


def test_normalize_mode_string():
    assert normalize_mode("paper") == TradingMode.PAPER
    assert normalize_mode("LIVE") == TradingMode.LIVE
    assert normalize_mode("mock") == TradingMode.MOCK


def test_normalize_mode_enum_passthrough():
    assert normalize_mode(TradingMode.BACKTEST) == TradingMode.BACKTEST


def test_normalize_mode_none_defaults_to_paper():
    assert normalize_mode(None) == TradingMode.PAPER


def test_normalize_mode_invalid_raises():
    with pytest.raises(ValueError, match="Unsupported mode"):
        normalize_mode("unknown")


def test_get_mode_policy_returns_policy():
    policy = get_mode_policy("paper")
    assert isinstance(policy, ModePolicy)
    assert policy.mode == TradingMode.PAPER
    assert policy.provider == "PaperTradingProvider"


def test_mode_policy_can_write_user_data():
    assert get_mode_policy("paper").can_write_user_data is True
    assert get_mode_policy("live").can_write_user_data is True
    assert get_mode_policy("mock").can_write_user_data is False
    assert get_mode_policy("backtest").can_write_user_data is True


def test_mode_policy_can_execute_orders():
    assert get_mode_policy("paper").can_execute_orders is True
    assert get_mode_policy("live").can_execute_orders is False
    assert get_mode_policy("mock").can_execute_orders is False


def test_all_modes_have_policies():
    for mode in TradingMode:
        assert mode in MODE_POLICIES
