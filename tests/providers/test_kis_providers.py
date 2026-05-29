import pytest

from api.brokers.kis.errors import KISConfigError
from api.providers.live import LiveTradingProvider
from api.providers.modes import get_mode_policy
from api.providers.paper import PaperTradingProvider


def test_paper_provider_import_smoke():
    assert PaperTradingProvider is not None


def test_live_provider_import_smoke():
    assert LiveTradingProvider is not None


def test_paper_provider_instantiates():
    provider = PaperTradingProvider(get_mode_policy("paper"))
    assert provider.name == "PaperTradingProvider"


def test_live_provider_instantiates():
    provider = LiveTradingProvider(get_mode_policy("live"))
    assert provider.name == "LiveTradingProvider"


def test_paper_provider_config_error_propagates(monkeypatch):
    import api.providers.paper as paper_module

    def raise_config_error(*, force_demo):
        raise KISConfigError("no credentials")

    monkeypatch.setattr(paper_module, "load_kis_config", raise_config_error)
    provider = PaperTradingProvider(get_mode_policy("paper"))

    with pytest.raises(KISConfigError):
        provider.sync_accounts(None)


def test_live_provider_config_error_propagates(monkeypatch):
    import api.providers.live as live_module

    def raise_config_error(*, force_demo):
        raise KISConfigError("no credentials")

    monkeypatch.setattr(live_module, "load_kis_config", raise_config_error)
    provider = LiveTradingProvider(get_mode_policy("live"))

    with pytest.raises(KISConfigError):
        provider.sync_accounts(None)
