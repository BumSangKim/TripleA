from __future__ import annotations

from datetime import date

from api.strategy.bottleneck_sector_engine import BottleneckSectorEngine
from api.strategy.indicator_plugins.base import PluginScore
from api.strategy_config import load_sector_taxonomy


class BottleneckIndicatorPlugin:
    plugin_name = "bottleneck"
    model_version = "bottleneck_plugin_v1"
    parameter_version = "default"

    def applies_to(self, sector_code: str) -> bool:
        sector = load_sector_taxonomy().get(sector_code, {})
        plugins = sector.get("specialized_plugins")
        if plugins is not None:
            return self.plugin_name in plugins
        return bool(sector.get("trade_items") or sector.get("indicators"))

    def score(self, conn, sector_code: str, as_of_date: date) -> PluginScore:
        if not self.applies_to(sector_code):
            return PluginScore(self.plugin_name, sector_code, 0.5, 0.0, 0.0, 0.0, {}, ["plugin_not_applicable"], as_of_date, self.model_version, self.parameter_version)
        match = next((item for item in BottleneckSectorEngine(conn).score(as_of_date) if item.sector_code == sector_code), None)
        if not match:
            return PluginScore(self.plugin_name, sector_code, 0.5, 0.2, 0.2, 0.0, {}, ["missing_bottleneck_data"], as_of_date, self.model_version, self.parameter_version)
        components = {
            "trade_score": match.trade_score / 100.0,
            "demand_score": match.demand_score / 100.0,
            "supply_score": match.supply_score / 100.0,
            "relative_strength_score": match.relative_strength_score / 100.0,
        }
        coverage = 1.0 if match.reasons and match.reasons != ["No bottleneck signal available"] else 0.25
        return PluginScore(
            self.plugin_name,
            sector_code,
            max(0.0, min(1.0, match.total_score / 100.0)),
            0.7 if coverage > 0.5 else 0.3,
            0.7 if coverage > 0.5 else 0.3,
            coverage,
            components,
            match.reasons,
            as_of_date,
            self.model_version,
            self.parameter_version,
        )
