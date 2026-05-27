from datetime import date

from api.strategy.indicator_plugins.base import PluginScore
from api.strategy.indicator_plugins.registry import IndicatorPluginRegistry


class DemoPlugin:
    plugin_name = "demo"
    model_version = "v1"
    def applies_to(self, sector_code): return sector_code == "A"
    def score(self, conn, sector_code, as_of_date): return PluginScore("demo", sector_code, 0.7, 0.8, 0.8, 1.0, {}, ["ok"], as_of_date, "v1", "p1")


class FailingPlugin(DemoPlugin):
    plugin_name = "fail"
    def score(self, conn, sector_code, as_of_date): raise RuntimeError("boom")


def test_plugin_registry_retrieves_and_falls_back_on_failure():
    registry = IndicatorPluginRegistry()
    registry.register_plugin(DemoPlugin())
    registry.register_plugin(FailingPlugin())
    assert len(registry.plugins_for_sector("A")) == 2
    assert registry.plugins_for_sector("B") == []
    scores = registry.score_sector_plugins(None, "A", date(2026, 5, 27))
    assert scores[0].score == 0.7
    assert scores[1].confidence == 0.2
