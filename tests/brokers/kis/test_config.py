import pytest

from api.brokers.kis.config import KISConfig, load_kis_config
from api.brokers.kis.errors import KISConfigError


def test_load_kis_config_prefers_demo_credentials():
    config = load_kis_config(
        {
            "KIS_ISDEMO": "true",
            "KIS_APP_KEY": "real_key",
            "KIS_APP_SECRET": "real_secret",
            "KIS_DEMO_APP_KEY": "demo_key",
            "KIS_DEMO_APP_SECRET": "demo_secret",
            "KIS_ACCOUNT_NO": "12345678-01",
            "KIS_ACCOUNT_TYPE": "ISA",
            "KIS_ACCOUNT_NAME": "Demo ISA",
        },
        force_demo=True,
    )
    assert config.is_demo is True
    assert config.app_key == "demo_key"
    assert config.app_secret == "demo_secret"
    assert config.cano == "12345678"
    assert config.account_product_code == "01"
    assert config.account_type == "ISA"
    assert config.account_name == "Demo ISA"


def test_load_kis_config_missing_credentials_raises():
    with pytest.raises(KISConfigError, match="credentials"):
        load_kis_config(
            {"KIS_ACCOUNT_NO": "12345678-01"},
            force_demo=True,
        )


def test_load_kis_config_missing_account_raises():
    with pytest.raises(KISConfigError, match="account"):
        load_kis_config(
            {
                "KIS_APP_KEY": "key",
                "KIS_APP_SECRET": "secret",
            },
            force_demo=False,
        )


def test_kis_config_base_url_demo():
    config = KISConfig(
        app_key="k",
        app_secret="s",
        cano="12345678",
        account_product_code="01",
        is_demo=True,
    )
    assert "vts" in config.base_url


def test_kis_config_base_url_live():
    config = KISConfig(
        app_key="k",
        app_secret="s",
        cano="12345678",
        account_product_code="01",
        is_demo=False,
    )
    assert "vts" not in config.base_url
