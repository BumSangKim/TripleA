from __future__ import annotations

from datetime import date

from api.strategy.indicator_plugins.base import PluginScore, SpecializedIndicatorPlugin, fallback_plugin_score


class IndicatorPluginRegistry:
    def __init__(self):
        self._plugins: list[SpecializedIndicatorPlugin] = []

    def register_plugin(self, plugin: SpecializedIndicatorPlugin) -> None:
        self._plugins.append(plugin)

    def plugins_for_sector(self, sector_code: str) -> list[SpecializedIndicatorPlugin]:
        return [plugin for plugin in self._plugins if plugin.applies_to(sector_code)]

    def score_sector_plugins(self, conn, sector_code: str, as_of_date: date) -> list[PluginScore]:
        scores: list[PluginScore] = []
        for plugin in self.plugins_for_sector(sector_code):
            try:
                scores.append(plugin.score(conn, sector_code, as_of_date))
            except Exception as exc:
                scores.append(fallback_plugin_score(plugin.plugin_name, sector_code, as_of_date, f"plugin_error:{type(exc).__name__}"))
        return scores
