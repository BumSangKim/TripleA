from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from api.features.intraday.collector import CollectionWarning, IntradayCollectionResult
from api.features.intraday.models import IntradayEvent, IntradayPriceSnapshot
from api.features.intraday.service import IntradayService


class FakeSnapshotReader:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.snapshots = [
            IntradayPriceSnapshot(
                id=1,
                symbol="005930",
                market="KRX",
                captured_at=datetime(2026, 6, 1, 10, 0, tzinfo=UTC),
                price=Decimal("70000"),
                open_price=Decimal("69000"),
                high_price=Decimal("70500"),
                low_price=Decimal("68800"),
                volume=Decimal("1000"),
                value_traded=Decimal("70000000"),
                change_rate=Decimal("1.5"),
                source="fixture",
                quality_score=0.99,
                is_stale=False,
            ),
            IntradayPriceSnapshot(
                id=2,
                symbol="005930",
                market="KRX",
                captured_at=datetime(2026, 6, 1, 10, 1, tzinfo=UTC),
                price=Decimal("70100"),
                source="fixture",
            ),
        ]

    def latest_snapshots(self, **kwargs: Any) -> list[IntradayPriceSnapshot]:
        self.calls.append(("latest_snapshots", kwargs))
        return self.snapshots[:1]

    def snapshots_for_symbol(self, **kwargs: Any) -> list[IntradayPriceSnapshot]:
        self.calls.append(("snapshots_for_symbol", kwargs))
        return self.snapshots


class FakeEventReader:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.events = [
            IntradayEvent(
                id=10,
                symbol="005930",
                market="KRX",
                event_type="SURGE",
                event_level="watch",
                detected_at=datetime(2026, 6, 1, 10, 2, tzinfo=UTC),
                lookback_minutes=3,
                base_price=Decimal("69000"),
                current_price=Decimal("71000"),
                change_rate=Decimal("2.9"),
                volume_ratio=Decimal("1.2"),
                reason_code="INTRADAY_SURGE_WATCH",
                message="fixture event",
                source_snapshot_id=2,
                acknowledged=False,
            )
        ]

    def recent_events(self, **kwargs: Any) -> list[IntradayEvent]:
        self.calls.append(("recent_events", kwargs))
        return self.events


class FakeAcknowledger:
    def __init__(self) -> None:
        self.known_ids = {10}

    def acknowledge_event(self, event_id: int) -> bool:
        return event_id in self.known_ids


class FakeCollector:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def collect_once(self, **kwargs: Any) -> IntradayCollectionResult:
        self.calls.append(kwargs)
        return IntradayCollectionResult(
            started_at="2026-06-01T10:00:00+00:00",
            finished_at="2026-06-01T10:00:01+00:00",
            requested_symbols=1,
            successful_symbols=1,
            failed_symbols=0,
            inserted_snapshots=1,
            warnings=[CollectionWarning("005930", "LOW_QUALITY", "fixture warning")],
            status="completed",
        )


def test_intraday_service_latest_and_symbol_snapshots_contract():
    service, snapshots, _, _, _ = _service()

    latest = service.latest_snapshots(market="KRX", symbols=["005930"], limit=50)
    symbol_rows = service.snapshots_for_symbol(
        symbol="005930",
        market="KRX",
        start_at=datetime(2026, 6, 1, 9, 59, tzinfo=UTC),
        end_at=datetime(2026, 6, 1, 10, 2, tzinfo=UTC),
        limit=1,
    )

    assert latest[0].to_dict()["price"] == 70000.0
    assert latest[0].to_dict()["change_rate"] == 1.5
    assert symbol_rows[0].to_dict()["id"] == 2
    assert snapshots.calls[0] == ("latest_snapshots", {"market": "KRX", "symbols": ["005930"], "limit": 50})


def test_intraday_service_recent_events_and_acknowledge_contract():
    service, _, events, _, _ = _service()

    recent = service.recent_events(event_type="SURGE", event_level="watch", acknowledged=False, limit=10)
    symbol_events = service.symbol_events(symbol="005930", limit=5)
    acknowledged = service.acknowledge_event(10)
    missing = service.acknowledge_event(99)

    assert recent[0].to_dict()["reason_code"] == "INTRADAY_SURGE_WATCH"
    assert symbol_events[0].to_dict()["symbol"] == "005930"
    assert events.calls[0][1]["acknowledged"] is False
    assert acknowledged.ok is True
    assert missing.ok is False
    assert missing.reason_code == "INTRADAY_EVENT_NOT_FOUND"


def test_intraday_service_collect_once_contract_is_display_only():
    service, _, _, _, collector = _service()

    payload = service.collect_once(config={"mode": "fixture"}, force=True)

    assert payload.to_dict()["inserted_snapshots"] == 1
    assert payload.to_dict()["warnings"][0]["reason_code"] == "LOW_QUALITY"
    assert collector.calls == [{"config": {"mode": "fixture"}, "force": True}]


def _service() -> tuple[IntradayService, FakeSnapshotReader, FakeEventReader, FakeAcknowledger, FakeCollector]:
    snapshots = FakeSnapshotReader()
    events = FakeEventReader()
    acknowledger = FakeAcknowledger()
    collector = FakeCollector()
    return (
        IntradayService(
            snapshot_reader=snapshots,
            event_reader=events,
            event_acknowledger=acknowledger,
            collector=collector,
        ),
        snapshots,
        events,
        acknowledger,
        collector,
    )
