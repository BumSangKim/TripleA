import sqlite3
from datetime import date

from api.strategy.indicator_plugins.bottleneck_plugin import BottleneckIndicatorPlugin


def test_bottleneck_plugin_applies_only_to_configured_sectors_and_falls_back():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    plugin = BottleneckIndicatorPlugin()
    assert plugin.applies_to("SEMICONDUCTOR") is True
    score = plugin.score(conn, "SEMICONDUCTOR", date(2026, 5, 27))
    assert score.plugin_name == "bottleneck"
    assert 0 <= score.score <= 1
