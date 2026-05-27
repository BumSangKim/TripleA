from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class IntradayMonitoringConfig:
    enabled: bool = True
    collection_interval_seconds: int = 60
    market_session_policy: str = "full_regular_session"
    timezone: str = "Asia/Seoul"
    regular_session_start: str = "09:00"
    regular_session_end: str = "15:30"
    universe_source: str = "investable_universe"
    universe_selector: str | None = None
    provider: str = "mock"
    lookback_windows_minutes: tuple[int, ...] = (1, 3, 5, 10, 15, 30)
    surge_thresholds: dict[str, float] | None = None
    drop_thresholds: dict[str, float] | None = None
    volume_spike_thresholds: dict[str, float] | None = None
    duplicate_suppression_minutes: int = 10
    stale_data_tolerance_seconds: int = 120
    max_symbols_per_batch: int = 100
    dry_run: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "surge_thresholds", self.surge_thresholds or {"watch": 2.0, "warning": 4.0, "critical": 7.0})
        object.__setattr__(self, "drop_thresholds", self.drop_thresholds or {"watch": -2.0, "warning": -4.0, "critical": -7.0})
        object.__setattr__(self, "volume_spike_thresholds", self.volume_spike_thresholds or {"watch": 2.0, "warning": 4.0, "critical": 7.0})


def load_intraday_config(path: str | Path = "config/intraday_monitoring.yaml") -> IntradayMonitoringConfig:
    config_path = Path(path)
    if not config_path.exists():
        return IntradayMonitoringConfig()
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    section = data.get("intraday_monitoring", data)
    return IntradayMonitoringConfig(
        enabled=bool(section.get("enabled", True)),
        collection_interval_seconds=int(section.get("collection_interval_seconds", 60)),
        market_session_policy=str(section.get("market_session_policy", "full_regular_session")),
        timezone=str(section.get("timezone", "Asia/Seoul")),
        regular_session_start=str(section.get("regular_session_start", "09:00")),
        regular_session_end=str(section.get("regular_session_end", "15:30")),
        universe_source=str(section.get("universe_source", "investable_universe")),
        universe_selector=_optional_string(section.get("universe_selector")),
        provider=str(section.get("provider", "mock")),
        lookback_windows_minutes=tuple(int(item) for item in section.get("lookback_windows_minutes", [1, 3, 5, 10, 15, 30])),
        surge_thresholds=_nested(section, ["price_change_rules", "surge"]),
        drop_thresholds=_nested(section, ["price_change_rules", "drop"]),
        volume_spike_thresholds=_nested(section, ["volume_rules", "volume_spike_ratio"]),
        duplicate_suppression_minutes=int(section.get("duplicate_suppression_minutes", 10)),
        stale_data_tolerance_seconds=int(section.get("stale_data_tolerance_seconds", 120)),
        max_symbols_per_batch=int(section.get("max_symbols_per_batch", 100)),
        dry_run=bool(section.get("dry_run", False)),
    )


def monitoring_thresholds_are_strategy_parameters() -> bool:
    return False


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _nested(data: dict[str, Any], keys: list[str]) -> dict[str, float] | None:
    value: Any = data
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    if not isinstance(value, dict):
        return None
    return {str(key): float(item) for key, item in value.items()}
