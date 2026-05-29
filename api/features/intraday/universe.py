from __future__ import annotations

from dataclasses import dataclass

from api.features.intraday.config import IntradayMonitoringConfig, load_intraday_config
from api.universe.loader import load_assets, load_universe_selectors
from api.universe.selector import resolve_all_selectors


@dataclass(frozen=True)
class IntradaySymbol:
    asset_id: str
    symbol: str
    market: str
    name: str
    asset_type: str


def resolve_intraday_universe(
    config: IntradayMonitoringConfig | None = None,
    *,
    assets: list[dict] | None = None,
    selectors: dict | None = None,
) -> list[IntradaySymbol]:
    config = config or load_intraday_config()
    if not config.enabled:
        return []
    assets = assets if assets is not None else load_assets("config/universe")
    selected = _select_assets(config, assets, selectors)
    result = []
    seen = set()
    for asset in selected:
        symbol = str(asset.get("symbol") or "").strip()
        market = str(asset.get("market") or "").strip()
        tradability = asset.get("tradability") or {}
        if not symbol or not market:
            continue
        if tradability.get("enabled_state") in {"disabled", "disabled_explicitly"}:
            continue
        if not _provider_supports_market(config.provider, market):
            continue
        key = (market, symbol)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            IntradaySymbol(
                asset_id=str(asset.get("asset_id")),
                symbol=symbol,
                market=market,
                name=str(asset.get("name") or symbol),
                asset_type=str(asset.get("asset_type") or ""),
            )
        )
    return result


def _select_assets(
    config: IntradayMonitoringConfig,
    assets: list[dict],
    selectors: dict | None,
) -> list[dict]:
    if not config.universe_selector:
        return assets
    selector_map = selectors if selectors is not None else load_universe_selectors("config/universe")["selectors"]
    return resolve_all_selectors(assets, selector_map).get(config.universe_selector, [])


def _provider_supports_market(provider: str, market: str) -> bool:
    if provider in {"kis", "kis_read_only", "mock"}:
        return market == "KRX"
    return False
