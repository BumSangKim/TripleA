from datetime import date

from api.domain.trade_data import TradeSeriesItem, TradeSnapshot
from api.strategy.bottleneck_sector_engine import BottleneckSectorEngine


class EmptyBottleneckConn:
    def execute(self, *args, **kwargs):
        return EmptyRows()


class EmptyRows:
    def fetchone(self):
        return None

    def fetchall(self):
        return []


class FakeTradeSnapshotReader:
    def __init__(self):
        self.calls = []

    def get_trade_snapshot(self, as_of_date: date, *, lookback_months: int = 60) -> TradeSnapshot:
        self.calls.append((as_of_date, lookback_months))
        return _snapshot(as_of_date, lookback_months, yoy=30.0)


def test_bottleneck_sector_engine_scores_trade_data_from_reader_without_sqlite_connection():
    reader = FakeTradeSnapshotReader()

    scores = {
        score.sector_code: score
        for score in BottleneckSectorEngine(EmptyBottleneckConn(), trade_snapshot_reader=reader).score(
            date(2024, 3, 10),
            lookback_months=12,
        )
    }

    assert reader.calls == [(date(2024, 3, 10), 12)]
    assert scores["SEMICONDUCTOR"].trade_score == 80.0
    assert any("HS_8542 trade YoY +30.0%" in reason for reason in scores["SEMICONDUCTOR"].reasons)


def test_bottleneck_sector_engine_accepts_explicit_trade_snapshot():
    scores = {
        score.sector_code: score
        for score in BottleneckSectorEngine(EmptyBottleneckConn()).score(
            date(2024, 3, 10),
            lookback_months=12,
            trade_snapshot=_snapshot(date(2024, 3, 10), 12, yoy=5.0),
        )
    }

    assert scores["SEMICONDUCTOR"].trade_score == 55.0


def test_bottleneck_sector_engine_uses_neutral_trade_score_without_reader_or_snapshot():
    scores = {
        score.sector_code: score
        for score in BottleneckSectorEngine(EmptyBottleneckConn()).score(
            date(2024, 3, 10),
            lookback_months=12,
        )
    }

    assert scores["SEMICONDUCTOR"].trade_score == 50.0


def _snapshot(as_of_date: date, lookback_months: int, *, yoy: float) -> TradeSnapshot:
    return TradeSnapshot(
        as_of_date=as_of_date,
        lookback_months=lookback_months,
        items=[
            TradeSeriesItem(
                period="2024-01",
                country="KR",
                flow="export",
                item_code="HS_8542",
                item_name="Semiconductors",
                amount_usd=100.0,
                quantity=None,
                unit=None,
                yoy=yoy,
                mom=None,
                source="test",
                release_date=date(2024, 2, 15),
            )
        ],
    )
