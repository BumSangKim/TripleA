from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import api.strategy.bottleneck_sector_engine as bottleneck_module
from api.domain.strategy_inputs import BottleneckIndicatorInput, BottleneckSnapshotInput
from api.domain.trade_data import TradeSeriesItem, TradeSnapshot
from api.strategy.bottleneck_sector_engine import BottleneckSectorEngine


class FakeBottleneckReader:
    def __init__(self, snapshot: BottleneckSnapshotInput):
        self.snapshot = snapshot
        self.read_dates: list[date] = []

    def read_bottleneck_snapshot(
        self,
        as_of_date: date,
        *,
        lookback_months: int,
    ) -> BottleneckSnapshotInput:
        self.read_dates.append(as_of_date)
        return self.snapshot


def _trade_snapshot() -> TradeSnapshot:
    return TradeSnapshot(
        as_of_date=date(2024, 3, 10),
        lookback_months=12,
        items=[
            TradeSeriesItem(
                period="2024-01",
                country="KR",
                flow="export",
                item_code="HS_8542",
                item_name=None,
                amount_usd=100.0,
                quantity=None,
                unit=None,
                yoy=35.0,
                mom=None,
                source="fake",
                release_date=date(2024, 2, 15),
            ),
        ],
    )


def _bottleneck_snapshot() -> BottleneckSnapshotInput:
    return BottleneckSnapshotInput(
        as_of_date=date(2024, 3, 10),
        lookback_months=12,
        indicators=[
            BottleneckIndicatorInput(
                indicator_key="RS_SMH_SPY",
                indicator_name="Relative strength",
                sector_code="SEMICONDUCTOR",
                value_date=date(2024, 2, 29),
                release_date=date(2024, 3, 1),
                value=90.0,
                unit="score",
                source="fake",
                layer="relative_strength",
            ),
        ],
    )


def test_bottleneck_reader_path_scores_deterministic_sector_signal():
    reader = FakeBottleneckReader(_bottleneck_snapshot())

    scores = {
        score.sector_code: score
        for score in BottleneckSectorEngine(bottleneck_snapshot_reader=reader).score(
            date(2024, 3, 10),
            lookback_months=12,
            trade_snapshot=_trade_snapshot(),
        )
    }

    assert reader.read_dates == [date(2024, 3, 10)]
    assert scores["SEMICONDUCTOR"].total_score == 74.0
    assert scores["SEMICONDUCTOR"].regime == "active"


def test_bottleneck_reader_path_no_longer_exposes_legacy_root_service():
    assert not hasattr(bottleneck_module, "get_bottleneck_snapshot")
    scores = BottleneckSectorEngine(
        bottleneck_snapshot_reader=FakeBottleneckReader(_bottleneck_snapshot())
    ).score(date(2024, 3, 10), lookback_months=12, trade_snapshot=_trade_snapshot())

    assert any(score.sector_code == "SEMICONDUCTOR" for score in scores)


def test_bottleneck_reader_path_missing_indicators_stays_neutral_safe():
    scores = {
        score.sector_code: score
        for score in BottleneckSectorEngine(
            bottleneck_snapshot_reader=FakeBottleneckReader(
                BottleneckSnapshotInput(
                    as_of_date=date(2024, 3, 10),
                    lookback_months=12,
                    indicators=[],
                )
            )
        ).score(
            date(2024, 3, 10),
            lookback_months=12,
            trade_snapshot=TradeSnapshot(date(2024, 3, 10), 12, []),
        )
    }

    assert scores["SEMICONDUCTOR"].total_score == 50.0
    assert scores["SEMICONDUCTOR"].regime == "inactive"
    assert scores["SEMICONDUCTOR"].reasons == ["No bottleneck signal available"]


def test_bottleneck_sector_engine_does_not_import_order_generation():
    path = Path("api/strategy/bottleneck_sector_engine.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = {"api.strategy.order_candidates"}

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert imports.isdisjoint(forbidden)
