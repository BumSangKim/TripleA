from api.providers.mock import BacktestProvider, MockProvider, TestProvider
from api.providers.modes import TradingMode, get_mode_policy


def test_mock_provider_instantiates():
    provider = MockProvider(get_mode_policy("mock"))
    assert provider.mode == TradingMode.MOCK
    assert provider.name == "MockProvider"


def test_test_provider_instantiates():
    provider = TestProvider(get_mode_policy("test"))
    assert provider.mode == TradingMode.TEST
    assert provider.name == "TestProvider"


def test_backtest_provider_instantiates():
    provider = BacktestProvider(get_mode_policy("backtest"))
    assert provider.mode == TradingMode.BACKTEST
    assert provider.name == "BacktestProvider"
    assert provider.capabilities.can_write_user_data is True
