from api.providers.modes import TradingMode
from api.providers.router import ProviderRouter, provider_router


def test_router_returns_provider_for_each_mode():
    router = ProviderRouter()
    for mode in TradingMode:
        provider = router.get(mode)
        assert provider.mode == mode


def test_router_get_by_string():
    router = ProviderRouter()
    provider = router.get("paper")
    assert provider.mode == TradingMode.PAPER


def test_router_list_all_modes():
    router = ProviderRouter()
    providers = router.list()
    modes = {p.mode for p in providers}
    assert modes == set(TradingMode)


def test_provider_router_singleton_is_importable():
    assert provider_router is not None
    assert isinstance(provider_router, ProviderRouter)
