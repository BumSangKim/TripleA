"""Read-only Korean Investment Securities OpenAPI client.

This module deliberately contains no order placement helpers. It is used by
providers to query account balances and normalize them into dashboard-friendly
snapshots.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REAL_BASE_URL = "https://openapi.koreainvestment.com:9443"
DEMO_BASE_URL = "https://openapivts.koreainvestment.com:29443"


class KISConfigError(RuntimeError):
    pass


class KISAPIError(RuntimeError):
    pass


@dataclass(frozen=True)
class KISConfig:
    app_key: str
    app_secret: str
    cano: str
    account_product_code: str
    is_demo: bool
    account_type: str = "GENERAL"
    account_name: str = "KIS Paper Account"

    @property
    def base_url(self) -> str:
        return DEMO_BASE_URL if self.is_demo else REAL_BASE_URL


@dataclass(frozen=True)
class KISPosition:
    code: str
    name: str
    quantity: float
    avg_price: float
    current_price: float
    market_value: float
    profit: float


@dataclass(frozen=True)
class KISBalanceSnapshot:
    account_masked: str
    total_value: float
    cash_value: float
    domestic_stock_value: float
    positions: list[KISPosition]
    message: str = ""


def _bool_env(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y"}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0").replace(",", "").strip() or "0")
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _first_decimal(row: Mapping[str, Any], keys: list[str]) -> Decimal:
    for key in keys:
        value = to_decimal(row.get(key))
        if value != 0:
            return value
    return Decimal("0")


def resolve_account(env: Mapping[str, str]) -> tuple[str, str]:
    cano = _clean(env.get("KIS_CANO"))
    product = _clean(env.get("KIS_ACNT_PRDT_CD"))
    account_no = _clean(env.get("KIS_ACCOUNT_NO"))

    if (not cano or not product) and account_no:
        digits = "".join(ch for ch in account_no if ch.isdigit())
        if len(digits) >= 10:
            cano = cano or digits[:8]
            product = product or digits[8:10]

    return cano, product


def mask_account(cano: str, product: str) -> str:
    if len(cano) < 4:
        return "<missing>"
    return f"{cano[:2]}****{cano[-2:]}-{product or '**'}"


def load_kis_config(
    env: Mapping[str, str] | None = None,
    *,
    force_demo: bool | None = None,
) -> KISConfig:
    load_dotenv(PROJECT_ROOT / ".env")
    source = env or os.environ
    is_demo = force_demo if force_demo is not None else _bool_env(source.get("KIS_ISDEMO"))

    if is_demo:
        app_key = _clean(source.get("KIS_DEMO_APP_KEY")) or _clean(source.get("KIS_APP_KEY"))
        app_secret = _clean(source.get("KIS_DEMO_APP_SECRET")) or _clean(source.get("KIS_APP_SECRET"))
    else:
        app_key = _clean(source.get("KIS_APP_KEY"))
        app_secret = _clean(source.get("KIS_APP_SECRET"))

    cano, product = resolve_account(source)
    if not app_key or not app_secret:
        raise KISConfigError("KIS app credentials are not configured")
    if len(cano) != 8 or len(product) != 2:
        raise KISConfigError("KIS account is not configured")

    return KISConfig(
        app_key=app_key,
        app_secret=app_secret,
        cano=cano,
        account_product_code=product,
        is_demo=is_demo,
        account_type=_clean(source.get("KIS_ACCOUNT_TYPE")) or "GENERAL",
        account_name=_clean(source.get("KIS_ACCOUNT_NAME")) or ("KIS Paper Account" if is_demo else "KIS Live Account"),
    )


class KISClient:
    def __init__(self, config: KISConfig, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()

    def issue_token(self) -> str:
        response = self.session.post(
            f"{self.config.base_url}/oauth2/tokenP",
            json={
                "grant_type": "client_credentials",
                "appkey": self.config.app_key,
                "appsecret": self.config.app_secret,
            },
            timeout=10,
        )
        data = self._json_or_raise(response)
        token = _clean(data.get("access_token"))
        if not token:
            raise KISAPIError(_clean(data.get("msg1")) or "KIS token response missing access_token")
        return token

    def _headers(self, token: str, tr_id: str) -> dict[str, str]:
        return {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": self.config.app_key,
            "appsecret": self.config.app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }

    def query_domestic_balance(self, token: str) -> dict[str, Any]:
        tr_id = "VTTC8434R" if self.config.is_demo else "TTTC8434R"
        response = self.session.get(
            f"{self.config.base_url}/uapi/domestic-stock/v1/trading/inquire-balance",
            headers=self._headers(token, tr_id),
            params={
                "CANO": self.config.cano,
                "ACNT_PRDT_CD": self.config.account_product_code,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "01",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "01",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            },
            timeout=10,
        )
        return self._json_or_raise(response)

    def fetch_domestic_balance(self) -> KISBalanceSnapshot:
        token = self.issue_token()
        data = self.query_domestic_balance(token)
        if _clean(data.get("rt_cd")) not in {"", "0"}:
            raise KISAPIError(_clean(data.get("msg1")) or "KIS balance request failed")
        return parse_domestic_balance(data, self.config)

    @staticmethod
    def _json_or_raise(response: requests.Response) -> dict[str, Any]:
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise KISAPIError(f"KIS HTTP error: {response.status_code}") from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise KISAPIError("KIS response was not JSON") from exc
        if not isinstance(data, dict):
            raise KISAPIError("KIS response JSON shape is not supported")
        return data


def parse_domestic_balance(data: Mapping[str, Any], config: KISConfig) -> KISBalanceSnapshot:
    output1 = data.get("output1") or []
    if isinstance(output1, Mapping):
        output1 = [output1]
    output2 = data.get("output2") or [{}]
    if isinstance(output2, Mapping):
        output2 = [output2]
    summary = output2[0] if output2 else {}

    positions: list[KISPosition] = []
    for row in output1:
        if not isinstance(row, Mapping):
            continue
        quantity = to_decimal(row.get("hldg_qty"))
        market_value = _first_decimal(row, ["evlu_amt", "market_value", "pchs_amt"])
        if quantity == 0 and market_value == 0:
            continue
        current_price = _first_decimal(row, ["prpr", "stck_prpr", "current_price"])
        if current_price == 0 and quantity > 0 and market_value > 0:
            current_price = market_value / quantity
        avg_price = _first_decimal(row, ["pchs_avg_pric", "avg_price"])
        positions.append(KISPosition(
            code=_clean(row.get("pdno")) or _clean(row.get("prdt_code")),
            name=_clean(row.get("prdt_name")) or _clean(row.get("name")),
            quantity=float(quantity),
            avg_price=float(avg_price),
            current_price=float(current_price),
            market_value=float(market_value),
            profit=float(_first_decimal(row, ["evlu_pfls_amt", "profit"])),
        ))

    domestic_stock_value = sum(position.market_value for position in positions)
    cash_value = float(_first_decimal(summary, ["dnca_tot_amt", "ord_psbl_cash", "cash_value"]))
    total_value = float(_first_decimal(summary, ["tot_evlu_amt", "nass_amt", "total_value"]))
    if total_value <= 0:
        total_value = domestic_stock_value + cash_value

    return KISBalanceSnapshot(
        account_masked=mask_account(config.cano, config.account_product_code),
        total_value=total_value,
        cash_value=cash_value,
        domestic_stock_value=domestic_stock_value,
        positions=positions,
        message=_clean(data.get("msg1")),
    )
