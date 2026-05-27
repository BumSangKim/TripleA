from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import requests

from api.kis import DEMO_BASE_URL, PROJECT_ROOT, REAL_BASE_URL, _bool_env, _clean, to_decimal
from api.market_data.models import PriceQuote


class ProviderUnavailableError(RuntimeError):
    pass


class UnsupportedProviderModeError(RuntimeError):
    pass


class PriceProvider:
    provider_name: str

    def get_current_price(self, *, symbol: str, market: str) -> PriceQuote:
        raise NotImplementedError


class MockPriceProvider(PriceProvider):
    provider_name = "mock"

    def get_current_price(self, *, symbol: str, market: str) -> PriceQuote:
        currency = "KRW" if market == "KRX" else "USD"
        return PriceQuote(
            symbol=symbol,
            market=market,
            price=Decimal("100.00"),
            currency=currency,
            provider=self.provider_name,
            as_of=datetime.now(UTC),
            raw={"source": "mock"},
        )


class KisReadOnlyPriceProvider(PriceProvider):
    provider_name = "kis_read_only"

    def __init__(self, *, app_key: str, app_secret: str, is_demo: bool, session: requests.Session | None = None):
        self.app_key = app_key
        self.app_secret = app_secret
        self.is_demo = is_demo
        self.base_url = DEMO_BASE_URL if is_demo else REAL_BASE_URL
        self.session = session or requests.Session()
        self._token: str | None = None

    def get_current_price(self, *, symbol: str, market: str) -> PriceQuote:
        if market != "KRX":
            raise ProviderUnavailableError(f"KIS quote adapter currently supports KRX only: {market}")
        token = self._token or self._issue_token()
        self._token = token
        data = self._query_domestic_quote(token=token, symbol=symbol)
        if _clean(data.get("rt_cd")) not in {"", "0"}:
            raise ProviderUnavailableError(_clean(data.get("msg1")) or "KIS quote request failed")
        output = data.get("output") or {}
        price = to_decimal(output.get("stck_prpr") or output.get("prpr"))
        if price <= 0:
            raise ProviderUnavailableError("KIS quote response did not include a positive price")
        return PriceQuote(
            symbol=symbol,
            market=market,
            price=price,
            currency="KRW",
            provider=self.provider_name,
            as_of=datetime.now(UTC),
            trade_date=_clean(output.get("stck_bsop_date")) or None,
            raw=data,
        )

    def _issue_token(self) -> str:
        response = self.session.post(
            f"{self.base_url}/oauth2/tokenP",
            json={
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
            },
            timeout=10,
        )
        data = _json_or_raise(response)
        token = _clean(data.get("access_token"))
        if not token:
            raise ProviderUnavailableError("KIS token response missing access_token")
        return token

    def _query_domestic_quote(self, *, token: str, symbol: str) -> dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "authorization": f"Bearer {token}",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
                "tr_id": "FHKST01010100",
                "custtype": "P",
            },
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": symbol,
            },
            timeout=10,
        )
        return _json_or_raise(response)


def get_default_price_provider(*, read_only: bool = True) -> PriceProvider:
    if not read_only:
        raise UnsupportedProviderModeError("Only read-only price providers are supported")
    provider = _clean(os.environ.get("TRIPLEA_PRICE_PROVIDER")).lower()
    if provider == "kis" or _clean(os.environ.get("RUN_LIVE_PRICE_SMOKE")) == "1":
        return _kis_provider_from_env()
    return MockPriceProvider()


def _kis_provider_from_env() -> KisReadOnlyPriceProvider:
    try:
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass

    is_demo = _bool_env(os.environ.get("KIS_ISDEMO"))
    app_key = _clean(os.environ.get("KIS_DEMO_APP_KEY") if is_demo else os.environ.get("KIS_APP_KEY"))
    app_secret = _clean(os.environ.get("KIS_DEMO_APP_SECRET") if is_demo else os.environ.get("KIS_APP_SECRET"))
    if not app_key:
        app_key = _clean(os.environ.get("KIS_APP_KEY"))
    if not app_secret:
        app_secret = _clean(os.environ.get("KIS_APP_SECRET"))
    if not app_key or not app_secret:
        raise ProviderUnavailableError("KIS app credentials are not configured")
    return KisReadOnlyPriceProvider(app_key=app_key, app_secret=app_secret, is_demo=is_demo)


def _json_or_raise(response: requests.Response) -> dict[str, Any]:
    try:
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise ProviderUnavailableError("price provider request failed") from exc
    except ValueError as exc:
        raise ProviderUnavailableError("price provider response was not JSON") from exc
    if not isinstance(data, dict):
        raise ProviderUnavailableError("price provider response shape is not supported")
    return data
