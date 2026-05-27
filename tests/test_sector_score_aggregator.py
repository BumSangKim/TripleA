from datetime import date

from api.strategy.common_sector_scoring_engine import CommonSectorScore
from api.strategy.indicator_plugins.base import PluginScore
from api.strategy.sector_score_aggregator import aggregate_sector_score


def _common():
    return CommonSectorScore("S", date(2026, 5, 27), .6, .6, .6, .2, .2, None, .7, None, .8, .7, .6, ["common"])


def test_sector_score_aggregates_common_and_plugins():
    common_only = aggregate_sector_score(_common(), [])
    plugin = PluginScore("p", "S", .9, .8, .8, 1, {}, ["plugin"], date(2026, 5, 27), "m", "p")
    with_plugin = aggregate_sector_score(_common(), [plugin], {"p": 1.0})
    missing = PluginScore("bad", "S", .5, .1, .1, 0, {}, ["missing"], date(2026, 5, 27), "m", "p")
    degraded = aggregate_sector_score(_common(), [missing])
    assert common_only.total_score == .6
    assert with_plugin.total_score > common_only.total_score
    assert degraded.confidence < common_only.confidence
    assert 0 <= with_plugin.total_score <= 1
