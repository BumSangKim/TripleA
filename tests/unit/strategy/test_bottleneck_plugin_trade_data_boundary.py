from datetime import date

import api.strategy.indicator_plugins.bottleneck_plugin as plugin_module
from api.strategy.indicator_plugins.bottleneck_plugin import BottleneckIndicatorPlugin
from api.strategy.types import SectorBottleneckScore


def test_bottleneck_plugin_passes_trade_snapshot_reader_to_engine(monkeypatch):
    captured = {}

    class FakeEngine:
        def __init__(self, conn, *, trade_snapshot_reader=None):
            captured["conn"] = conn
            captured["trade_snapshot_reader"] = trade_snapshot_reader

        def score(self, as_of_date):
            captured["as_of_date"] = as_of_date
            return [
                SectorBottleneckScore(
                    sector_code="SEMICONDUCTOR",
                    total_score=80.0,
                    trade_score=80.0,
                    demand_score=50.0,
                    supply_score=50.0,
                    relative_strength_score=50.0,
                    regime="active",
                    reasons=["fake"],
                )
            ]

    monkeypatch.setattr(plugin_module, "BottleneckSectorEngine", FakeEngine)
    reader = object()
    conn = object()

    result = BottleneckIndicatorPlugin().score(
        conn,
        "SEMICONDUCTOR",
        date(2024, 3, 10),
        trade_snapshot_reader=reader,
    )

    assert captured["conn"] is conn
    assert captured["trade_snapshot_reader"] is reader
    assert result.sector_code == "SEMICONDUCTOR"
    assert result.score == 0.8
