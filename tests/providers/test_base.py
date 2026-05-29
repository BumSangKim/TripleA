from api.providers.base import BaseDataProvider, ProviderCapabilities
from api.providers.modes import TradingMode, get_mode_policy


def test_provider_capabilities_from_policy():
    policy = get_mode_policy("paper")
    provider = BaseDataProvider(policy)
    caps = provider.capabilities
    assert isinstance(caps, ProviderCapabilities)
    assert caps.mode == TradingMode.PAPER
    assert caps.can_write_user_data is True
    assert caps.can_execute_orders is True
    assert caps.external_api is True


def test_provider_mode_info():
    policy = get_mode_policy("mock")
    provider = BaseDataProvider(policy)
    info = provider.mode_info()
    assert info.mode == TradingMode.MOCK
    assert info.canWriteUserData is False
    assert info.canExecuteOrders is False


def test_assert_user_write_allowed_raises_for_readonly():
    policy = get_mode_policy("mock")
    provider = BaseDataProvider(policy)
    try:
        provider.assert_user_write_allowed()
        assert False, "should have raised"
    except PermissionError:
        pass


def test_assert_user_write_allowed_passes_for_paper():
    policy = get_mode_policy("paper")
    provider = BaseDataProvider(policy)
    provider.assert_user_write_allowed()  # should not raise
