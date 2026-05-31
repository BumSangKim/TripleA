from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from dotenv import load_dotenv

from .errors import KISConfigError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REAL_BASE_URL = "https://openapi.koreainvestment.com:9443"
DEMO_BASE_URL = "https://openapivts.koreainvestment.com:29443"


def _bool_env(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y"}


def _clean(value: Any) -> str:
    return str(value or "").strip()


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
