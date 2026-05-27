from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class PluginScore:
    plugin_name: str
    sector_code: str
    score: float
    confidence: float
    data_quality: float
    coverage: float
    components: dict[str, float]
    reason_codes: list[str]
    as_of_date: date
    model_version: str
    parameter_version: str


class SpecializedIndicatorPlugin(Protocol):
    plugin_name: str
    model_version: str

    def applies_to(self, sector_code: str) -> bool:
        ...

    def score(self, conn, sector_code: str, as_of_date: date) -> PluginScore:
        ...


def fallback_plugin_score(plugin_name: str, sector_code: str, as_of_date: date, reason: str) -> PluginScore:
    return PluginScore(plugin_name, sector_code, 0.5, 0.2, 0.2, 0.0, {}, [reason], as_of_date, "fallback", "default")
