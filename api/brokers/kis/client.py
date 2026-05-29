from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

import requests

from .config import KISConfig, mask_account
from .errors import KISAPIError, KISNetworkError
from .models import KISBalanceSnapshot, KISPosition


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


def classify_kis_asset(code: str, name: str) -> str:
    upper_name = name.upper()
    bond_keywords = [
        "채권",
        "국고채",
        "국채",
        "회사채",
        "통안채",
        "단기금융",
        "머니마켓",
        "MMF",
        "CD금리",
        "KOFR",
    ]
    if any(keyword in upper_name for keyword in bond_keywords):
        return "채권"

    etf_prefixes = [
        "ACE ",
        "ARIRANG ",
        "HANARO ",
        "KBSTAR ",
        "KODEX ",
        "KOSEF ",
        "PLUS ",
        "RISE ",
        "SOL ",
        "TIGER ",
        "TIMEFOLIO ",
        "TREX ",
    ]
    if any(upper_name.startswith(prefix) for prefix in etf_prefixes):
        return "ETF"

    if code.startswith(("1", "2", "3", "4", "5", "6")) and any(prefix.strip() in upper_name for prefix in etf_prefixes):
        return "ETF"

    return "국내주식"


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
        code = _clean(row.get("pdno")) or _clean(row.get("prdt_code"))
        name = _clean(row.get("prdt_name")) or _clean(row.get("name"))
        positions.append(KISPosition(
            code=code,
            name=name,
            quantity=float(quantity),
            avg_price=float(avg_price),
            current_price=float(current_price),
            market_value=float(market_value),
            profit=float(_first_decimal(row, ["evlu_pfls_amt", "profit"])),
            asset_class=classify_kis_asset(code, name),
        ))

    domestic_stock_value = sum(p.market_value for p in positions if p.asset_class == "국내주식")
    bond_value = sum(p.market_value for p in positions if p.asset_class == "채권")
    etf_value = sum(p.market_value for p in positions if p.asset_class == "ETF")
    cash_value = float(_first_decimal(summary, ["dnca_tot_amt", "ord_psbl_cash", "cash_value"]))
    total_value = float(_first_decimal(summary, ["tot_evlu_amt", "nass_amt", "total_value"]))
    if total_value <= 0:
        total_value = domestic_stock_value + bond_value + etf_value + cash_value

    return KISBalanceSnapshot(
        account_masked=mask_account(config.cano, config.account_product_code),
        total_value=total_value,
        cash_value=cash_value,
        domestic_stock_value=domestic_stock_value,
        positions=positions,
        bond_value=bond_value,
        etf_value=etf_value,
        message=_clean(data.get("msg1")),
    )


class KISClient:
    def __init__(self, config: KISConfig, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()

    def issue_token(self) -> str:
        try:
            response = self.session.post(
                f"{self.config.base_url}/oauth2/tokenP",
                json={
                    "grant_type": "client_credentials",
                    "appkey": self.config.app_key,
                    "appsecret": self.config.app_secret,
                },
                timeout=10,
            )
        except requests.RequestException as exc:
            raise KISNetworkError("KIS token request failed") from exc
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
        try:
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
        except requests.RequestException as exc:
            raise KISNetworkError("KIS balance request failed") from exc
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
