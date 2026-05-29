import pytest
import requests

from api.brokers.kis.client import KISClient, classify_kis_asset, parse_domestic_balance
from api.brokers.kis.config import KISConfig
from api.brokers.kis.errors import KISNetworkError


def test_client_import_smoke():
    assert KISClient is not None
    assert classify_kis_asset is not None
    assert parse_domestic_balance is not None


def test_client_instantiates_without_network():
    config = KISConfig(
        app_key="key",
        app_secret="secret",
        cano="12345678",
        account_product_code="01",
        is_demo=True,
    )
    client = KISClient(config)
    assert client.config is config


def test_client_masks_network_errors():
    config = KISConfig(
        app_key="key",
        app_secret="secret",
        cano="12345678",
        account_product_code="01",
        is_demo=True,
    )

    class FailingSession:
        def post(self, *args, **kwargs):
            raise requests.Timeout("request timed out")

    with pytest.raises(KISNetworkError) as exc:
        KISClient(config, session=FailingSession()).issue_token()

    assert "KIS token request failed" in str(exc.value)


def test_classify_kis_asset():
    assert classify_kis_asset("005930", "삼성전자") == "국내주식"
    assert classify_kis_asset("069500", "KODEX 200") == "ETF"
    assert classify_kis_asset("476800", "ACE 국고채10년") == "채권"
