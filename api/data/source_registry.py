from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


ALLOWED_SOURCE_TYPES = {"market_price", "current_quote", "macro", "fx", "interest_rate", "export_import"}
ALLOWED_FALLBACK_POLICIES = {
    "reduce_signal_weight",
    "hold",
    "review_required",
    "use_conservative_fallback",
    "risk_reduce_only",
}


class DataSourceConfigError(ValueError):
    pass


@dataclass(frozen=True)
class DataSource:
    source_id: str
    source_type: str
    provider: str
    symbols_or_indicators: list[str]
    frequency: str
    expected_lag_days: int
    stale_after_days: int
    enabled: bool
    requires_secret: bool
    fallback_policy: str

    @property
    def secret_env_var(self) -> str:
        return f"{self.provider.upper()}_API_KEY"

    def can_execute(self, env: dict[str, str] | None = None) -> bool:
        source = env if env is not None else os.environ
        if not self.enabled:
            return False
        if self.requires_secret and not source.get(self.secret_env_var):
            return False
        return True


def load_data_sources(path: str | Path = "config/data_sources.yml") -> list[DataSource]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    validate_data_source_config(data)
    return [_parse_source(item) for item in data["sources"]]


def validate_data_source_config(data: dict[str, Any]) -> None:
    if not isinstance(data.get("sources"), list) or not data["sources"]:
        raise DataSourceConfigError("sources must be a non-empty list")
    seen = set()
    for item in data["sources"]:
        if not isinstance(item, dict):
            raise DataSourceConfigError("source entry must be an object")
        for field in [
            "source_id",
            "source_type",
            "provider",
            "symbols_or_indicators",
            "frequency",
            "expected_lag_days",
            "stale_after_days",
            "enabled",
            "requires_secret",
            "fallback_policy",
        ]:
            if field not in item:
                raise DataSourceConfigError(f"{item.get('source_id', '<unknown>')}: missing {field}")
        if item["source_id"] in seen:
            raise DataSourceConfigError(f"duplicate source_id: {item['source_id']}")
        seen.add(item["source_id"])
        if item["source_type"] not in ALLOWED_SOURCE_TYPES:
            raise DataSourceConfigError(f"{item['source_id']}: invalid source_type")
        if item["fallback_policy"] not in ALLOWED_FALLBACK_POLICIES:
            raise DataSourceConfigError(f"{item['source_id']}: invalid fallback_policy")
        if not isinstance(item["symbols_or_indicators"], list) or not item["symbols_or_indicators"]:
            raise DataSourceConfigError(f"{item['source_id']}: symbols_or_indicators must be non-empty")
        if item["expected_lag_days"] < 0 or item["stale_after_days"] < 0:
            raise DataSourceConfigError(f"{item['source_id']}: lag/stale days must be non-negative")


def executable_sources(
    sources: list[DataSource],
    *,
    source_type: str | None = None,
    env: dict[str, str] | None = None,
) -> list[DataSource]:
    return [
        source
        for source in sources
        if (source_type is None or source.source_type == source_type) and source.can_execute(env)
    ]


def _parse_source(item: dict[str, Any]) -> DataSource:
    return DataSource(
        source_id=str(item["source_id"]),
        source_type=str(item["source_type"]),
        provider=str(item["provider"]),
        symbols_or_indicators=[str(value) for value in item["symbols_or_indicators"]],
        frequency=str(item["frequency"]),
        expected_lag_days=int(item["expected_lag_days"]),
        stale_after_days=int(item["stale_after_days"]),
        enabled=bool(item["enabled"]),
        requires_secret=bool(item["requires_secret"]),
        fallback_policy=str(item["fallback_policy"]),
    )
