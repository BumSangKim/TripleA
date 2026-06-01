from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Sequence

import yaml


DEFAULT_WEIGHT_SUM_TOLERANCE = 0.000001
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PORTFOLIO_CONFIG_PATH = PROJECT_ROOT / "config" / "backtests" / "sector_component_sector_portfolios.yaml"
DEFAULT_SECTOR_TAXONOMY_PATH = PROJECT_ROOT / "config" / "sector_taxonomy.yaml"
DEFAULT_INVESTMENT_UNIVERSE_PATH = PROJECT_ROOT / "config" / "investment_universe.yaml"


@dataclass(frozen=True)
class SectorPortfolioAsset:
    asset_code: str
    weight: float
    role: str = "primary_proxy"
    name: str | None = None
    category: str | None = None
    market: str | None = None
    exchange: str | None = None
    currency: str | None = None
    min_weight: float | None = None
    max_weight: float | None = None
    risk_tags: tuple[str, ...] = field(default_factory=tuple)
    notes: str | None = None

    def __post_init__(self) -> None:
        asset_code = self.asset_code.strip().upper() if isinstance(self.asset_code, str) else self.asset_code
        role = self.role.strip() if isinstance(self.role, str) else self.role
        if not asset_code:
            raise ValueError("asset_code must be non-empty")
        if not role:
            raise ValueError("role must be non-empty")
        weight = float(self.weight)
        if weight < 0:
            raise ValueError("asset weight must be non-negative")
        min_weight = None if self.min_weight is None else float(self.min_weight)
        max_weight = None if self.max_weight is None else float(self.max_weight)
        if min_weight is not None and weight < min_weight:
            raise ValueError("asset weight must not be below min_weight")
        if max_weight is not None and weight > max_weight:
            raise ValueError("asset weight must not exceed max_weight")
        object.__setattr__(self, "asset_code", asset_code)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "weight", weight)
        object.__setattr__(self, "min_weight", min_weight)
        object.__setattr__(self, "max_weight", max_weight)
        _coerce_tuple(self, "risk_tags")

    def to_dict(self) -> dict[str, Any]:
        return _serialize_dataclass(self)


@dataclass(frozen=True)
class SectorComponentSectorPortfolio:
    """Diagnostic sector sleeve fixture, not an account allocation or order instruction."""

    sector_id: str
    display_name: str
    portfolio_id: str
    assets: tuple[SectorPortfolioAsset, ...]
    enabled: bool = True
    display_order: int = 0
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    semantics: str = "diagnostic_sector_sleeve_fixture"

    def __post_init__(self) -> None:
        sector_id = self.sector_id.strip().upper() if isinstance(self.sector_id, str) else self.sector_id
        if not sector_id:
            raise ValueError("sector_id must be non-empty")
        if sector_id != self.sector_id:
            object.__setattr__(self, "sector_id", sector_id)
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise ValueError("display_name must be non-empty")
        if not isinstance(self.portfolio_id, str) or not self.portfolio_id.strip():
            raise ValueError("portfolio_id must be non-empty")
        _coerce_tuple(self, "assets")
        _coerce_tuple(self, "reason_codes")
        _coerce_tuple(self, "warnings")
        if not self.assets:
            raise ValueError("portfolio assets must not be empty")
        validate_weight_sum(self.assets)

    @property
    def asset_count(self) -> int:
        return len(self.assets)

    def to_dict(self) -> dict[str, Any]:
        return _serialize_dataclass(self)


def validate_weight_sum(
    assets: Sequence[SectorPortfolioAsset],
    *,
    tolerance: float = DEFAULT_WEIGHT_SUM_TOLERANCE,
) -> None:
    total = sum(float(asset.weight) for asset in assets)
    if abs(total - 1.0) > tolerance:
        raise ValueError("sector portfolio asset weights must sum to 1.0")


def load_sector_component_sector_portfolios(
    path: str | Path = DEFAULT_PORTFOLIO_CONFIG_PATH,
    *,
    taxonomy_path: str | Path = DEFAULT_SECTOR_TAXONOMY_PATH,
    investment_universe_path: str | Path = DEFAULT_INVESTMENT_UNIVERSE_PATH,
) -> tuple[SectorComponentSectorPortfolio, ...]:
    raw = _load_yaml(Path(path))
    taxonomy_raw = _load_yaml(Path(taxonomy_path))
    investment_universe_raw = _load_yaml(Path(investment_universe_path))
    return parse_sector_component_sector_portfolios(
        raw,
        taxonomy_raw=taxonomy_raw,
        investment_universe_raw=investment_universe_raw,
    )


def parse_sector_component_sector_portfolios(
    raw: dict[str, Any],
    *,
    taxonomy_raw: dict[str, Any] | None = None,
    investment_universe_raw: dict[str, Any] | None = None,
) -> tuple[SectorComponentSectorPortfolio, ...]:
    taxonomy = _taxonomy_sectors(taxonomy_raw or {})
    investment_asset_codes = _investment_asset_codes(investment_universe_raw or {})
    portfolios_raw = _portfolio_items(raw)
    if not isinstance(portfolios_raw, list) or not portfolios_raw:
        raise ValueError("sector component portfolio config requires non-empty portfolios")
    portfolios = [
        _parse_portfolio(item, taxonomy=taxonomy, investment_asset_codes=investment_asset_codes)
        for item in portfolios_raw
    ]
    return tuple(sorted(portfolios, key=lambda item: (item.display_order, item.sector_id, item.portfolio_id)))


def enabled_sector_component_portfolios(
    portfolios: Sequence[SectorComponentSectorPortfolio],
) -> tuple[SectorComponentSectorPortfolio, ...]:
    return tuple(sorted((portfolio for portfolio in portfolios if portfolio.enabled), key=lambda item: (item.display_order, item.sector_id, item.portfolio_id)))


def _parse_portfolio(
    raw: dict[str, Any],
    *,
    taxonomy: dict[str, Any],
    investment_asset_codes: set[str],
) -> SectorComponentSectorPortfolio:
    sector_id = _required_text(raw, "sector_id").upper()
    if sector_id not in taxonomy:
        raise ValueError(f"unknown sector_id: {sector_id}")
    taxonomy_assets = {str(asset).strip().upper() for asset in taxonomy.get(sector_id, {}).get("assets", ())}
    assets_raw = raw.get("assets")
    if not isinstance(assets_raw, list) or not assets_raw:
        raise ValueError(f"{sector_id}: assets must be a non-empty list")
    assets = tuple(_parse_asset(item) for item in assets_raw)
    for asset in assets:
        if asset.asset_code not in taxonomy_assets:
            raise ValueError(f"{sector_id}: asset not in taxonomy assets: {asset.asset_code}")
    warnings = list(raw.get("warnings") or ())
    for asset in assets:
        if investment_asset_codes and asset.asset_code not in investment_asset_codes:
            warnings.append(f"ASSET_NOT_IN_INVESTMENT_UNIVERSE_REVIEW_REQUIRED:{asset.asset_code}")
    return SectorComponentSectorPortfolio(
        sector_id=sector_id,
        display_name=_required_text(raw, "display_name"),
        portfolio_id=_required_text(raw, "portfolio_id"),
        enabled=bool(raw.get("enabled", True)),
        display_order=int(raw.get("display_order", 0)),
        assets=assets,
        reason_codes=tuple(raw.get("reason_codes") or ()),
        warnings=tuple(warnings),
    )


def _portfolio_items(raw: dict[str, Any]) -> list[dict[str, Any]] | None:
    portfolios = raw.get("portfolios")
    if portfolios is not None:
        return portfolios
    sectors = raw.get("sectors")
    if sectors is None:
        return None
    if not isinstance(sectors, list):
        raise ValueError("sector trade reference config requires sectors to be a list")
    _validate_trade_reference_policy(raw)
    return [_normalize_reference_sector(item, index=index, raw=raw) for index, item in enumerate(sectors)]


def _normalize_reference_sector(raw_sector: dict[str, Any], *, index: int, raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw_sector, dict):
        raise ValueError("sector trade reference sector must be a mapping")
    version = raw.get("portfolio_version")
    classification = raw.get("classification")
    reason_codes = list(raw_sector.get("reason_codes") or ())
    if isinstance(classification, str) and classification.strip():
        reason_codes.append(classification.strip().upper())
    if isinstance(version, str) and version.strip():
        reason_codes.append(f"PORTFOLIO_VERSION:{version.strip()}")
    return {
        "sector_id": raw_sector.get("sector_id"),
        "display_name": raw_sector.get("display_name"),
        "portfolio_id": raw_sector.get("portfolio_id"),
        "enabled": raw_sector.get("enabled", True),
        "display_order": raw_sector.get("display_order", (index + 1) * 10),
        "assets": raw_sector.get("assets"),
        "reason_codes": reason_codes,
        "warnings": raw_sector.get("warnings") or (),
    }


def _parse_asset(raw: dict[str, Any]) -> SectorPortfolioAsset:
    weight = raw.get("weight", raw.get("base_weight"))
    if weight is None:
        raise ValueError("portfolio asset requires weight or base_weight")
    return SectorPortfolioAsset(
        asset_code=_required_text(raw, "asset_code"),
        weight=float(weight),
        role=_required_text(raw, "role") if raw.get("role") is not None else "primary_proxy",
        name=_optional_text(raw.get("name")),
        category=_optional_text(raw.get("category")),
        market=_optional_text(raw.get("market")),
        exchange=_optional_text(raw.get("exchange")),
        currency=_optional_text(raw.get("currency")),
        min_weight=None if raw.get("min_weight") is None else float(raw.get("min_weight")),
        max_weight=None if raw.get("max_weight") is None else float(raw.get("max_weight")),
        risk_tags=tuple(str(item).strip() for item in raw.get("risk_tags") or () if str(item).strip()),
        notes=_optional_text(raw.get("notes")),
    )


def _validate_trade_reference_policy(raw: dict[str, Any]) -> None:
    policy = raw.get("global_policy") or {}
    if policy.get("automatic_execution_allowed") is not False:
        raise ValueError("trade reference portfolios must explicitly disallow automatic execution")
    expected_sum = float(policy.get("base_weights_must_sum_to", 1.0))
    if abs(expected_sum - 1.0) > DEFAULT_WEIGHT_SUM_TOLERANCE:
        raise ValueError("trade reference base_weights_must_sum_to must be 1.0")


def _taxonomy_sectors(raw: dict[str, Any]) -> dict[str, Any]:
    sectors = raw.get("sectors", raw)
    if not isinstance(sectors, dict):
        raise ValueError("sector taxonomy must be a mapping")
    return {str(key).strip().upper(): value or {} for key, value in sectors.items()}


def _investment_asset_codes(raw: dict[str, Any]) -> set[str]:
    codes: set[str] = set()
    for asset in raw.get("assets", ()) or ():
        code = asset.get("asset_code")
        if code:
            codes.add(str(code).strip().upper())
    for universe in (raw.get("universes") or {}).values():
        for asset in universe.get("assets", ()) or ():
            code = asset.get("asset_code")
            if code:
                codes.add(str(code).strip().upper())
    return codes


def _required_text(raw: dict[str, Any], field_name: str) -> str:
    value = raw.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text")
    return value.strip()


def _optional_text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _coerce_tuple(instance: Any, field_name: str) -> None:
    value = getattr(instance, field_name)
    if not isinstance(value, tuple):
        object.__setattr__(instance, field_name, tuple(value or ()))


def _serialize_dataclass(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _serialize_dataclass(item) for key, item in asdict(value).items()}
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_serialize_dataclass(item) for item in value]
    if isinstance(value, list):
        return [_serialize_dataclass(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_dataclass(item) for key, item in value.items()}
    return value
