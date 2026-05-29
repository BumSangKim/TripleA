import os
import sqlite3
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from api.db.initialize import initialize_database as ensure_dashboard_tables
from api.features.intraday.alert import process_intraday_events
from api.features.intraday.collector import collect_intraday_once
from api.features.intraday.config import IntradayMonitoringConfig
from api.features.intraday.detector import detect_events_for_snapshot
from api.features.intraday.models import IntradayEvent, IntradayPriceSnapshot
from api.features.intraday.provider import MockIntradayProvider
from api.features.intraday.repository import insert_snapshot, latest_snapshots, recent_events
from api.features.intraday.universe import IntradaySymbol
from api.features.targets.schemas import TargetItem
from api.features.rebalancing.repository import get_rebalancing_suggestions
from api.strategy.common_sector_scoring_engine import CommonSectorScore
from api.strategy.indicator_plugins.base import PluginScore
from api.strategy.macro_engine import MacroEngine
from api.strategy.risk_budget_engine import RiskBudgetEngine, RiskBudgetPolicy, RiskBucketRule
from api.strategy.sector_score_aggregator import aggregate_sector_score
from api.strategy.triplea_allocator import TripleAAllocator


def _conn(path=":memory:"):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _macro_conn():
    conn = _conn()
    conn.execute(
        """
        CREATE TABLE indicators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            indicator TEXT,
            value REAL,
            unit TEXT,
            date TEXT,
            source TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO indicators (indicator, value, unit, date, source) VALUES (?, ?, ?, ?, 'test')",
        [("VIXCLS", 15.0, "pt", "2024-01-02"), ("ISM_PMI", 52.0, "pt", "2024-01-02")],
    )
    return conn


def _event():
    return IntradayEvent(
        symbol="005930",
        market="KRX",
        event_type="SURGE",
        event_level="WARNING",
        detected_at=datetime(2026, 5, 27, 10, 31, tzinfo=UTC),
        lookback_minutes=5,
        base_price=Decimal("100"),
        current_price=Decimal("105"),
        change_rate=Decimal("5"),
        volume_ratio=Decimal("2"),
        reason_code="INTRADAY_SURGE_PRICE_CHANGE",
        message="surge detected",
    )


def test_intraday_events_do_not_modify_macro_regime_scores():
    conn = _macro_conn()
    before = MacroEngine(conn).evaluate(date(2024, 1, 3))

    process_intraday_events(conn, [_event()], IntradayMonitoringConfig())
    after = MacroEngine(conn).evaluate(date(2024, 1, 3))

    assert after == before


def test_intraday_events_do_not_modify_sector_scores():
    conn = _conn()
    common = CommonSectorScore("SEMICONDUCTOR", date(2026, 5, 27), .6, .6, .6, .2, .2, None, .7, None, .8, .7, .6, ["common"])
    plugin = PluginScore("p", "SEMICONDUCTOR", .9, .8, .8, 1, {}, ["plugin"], date(2026, 5, 27), "m", "p")
    before = aggregate_sector_score(common, [plugin], {"p": 1.0})

    process_intraday_events(conn, [_event()], IntradayMonitoringConfig())
    after = aggregate_sector_score(common, [plugin], {"p": 1.0})

    assert after == before


def test_intraday_events_do_not_modify_risk_budget_outputs():
    conn = _conn()
    engine = RiskBudgetEngine()
    kwargs = {
        "asset_weights": {"SPY": 0.90, "TLT": 0.10, "CASH_KRW": 0.0},
        "asset_to_bucket": {"SPY": "AGGRESSIVE_ALPHA", "TLT": "DEFENSIVE_CORE", "CASH_KRW": "LIQUIDITY"},
        "policy": RiskBudgetPolicy(
            buckets={
                "AGGRESSIVE_ALPHA": RiskBucketRule(target=0.45, min=0.25, max=0.65),
                "DEFENSIVE_CORE": RiskBucketRule(target=0.40, min=0.25, max=0.60),
                "LIQUIDITY": RiskBucketRule(target=0.15, min=0.05, max=0.30),
            }
        ),
    }
    before = engine.apply(**kwargs)

    process_intraday_events(conn, [_event()], IntradayMonitoringConfig())
    after = engine.apply(**kwargs)

    assert after == before


def test_intraday_events_do_not_modify_allocation_outputs():
    conn = _conn()
    before = TripleAAllocator(conn, risk_profile="balanced").allocate(date(2024, 1, 31))

    process_intraday_events(conn, [_event()], IntradayMonitoringConfig())
    after = TripleAAllocator(conn, risk_profile="balanced").allocate(date(2024, 1, 31))

    assert after.final_weights == before.final_weights
    assert after.bucket_weights == before.bucket_weights
    assert after.macro_regime == before.macro_regime


def test_intraday_events_do_not_modify_rebalancing_outputs():
    conn = _conn()
    targets = [
        TargetItem(asset_class="국내주식", currentRatio=35.0, targetRatio=30.0, deviation=5.0, level="warning"),
        TargetItem(asset_class="현금", currentRatio=10.0, targetRatio=15.0, deviation=-5.0, level="warning"),
    ]
    before = get_rebalancing_suggestions(targets)

    process_intraday_events(conn, [_event()], IntradayMonitoringConfig())
    after = get_rebalancing_suggestions(targets)

    assert after == before


def test_intraday_events_do_not_generate_order_candidates_or_drafts(tmp_path, monkeypatch):
    db_path = str(tmp_path / "isolation.db")
    monkeypatch.setattr("api.db.connection.DB_PATH", db_path)
    ensure_dashboard_tables()
    conn = _conn(db_path)

    process_intraday_events(conn, [_event()], IntradayMonitoringConfig())

    assert conn.execute("SELECT COUNT(*) AS c FROM order_drafts").fetchone()["c"] == 0
    assert conn.execute("SELECT COUNT(*) AS c FROM order_items").fetchone()["c"] == 0


def test_intraday_api_import_does_not_trigger_collection_or_strategy_side_effects(tmp_path, monkeypatch):
    db_path = str(tmp_path / "api_import.db")
    os.environ["DB_PATH"] = db_path
    import api.db.connection as api_db
    from api.main import app

    monkeypatch.setattr(api_db, "DB_PATH", db_path)
    with TestClient(app):
        pass
    conn = _conn(db_path)

    intraday_tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'intraday_%'").fetchall()
    }
    assert intraday_tables == set()
    assert conn.execute("SELECT COUNT(*) AS c FROM order_drafts").fetchone()["c"] == 0
    del os.environ["DB_PATH"]


class ScenarioProvider(MockIntradayProvider):
    def __init__(self, prices_by_time):
        super().__init__()
        self.prices_by_time = prices_by_time

    def fetch_snapshot(self, symbol, *, captured_at, config):
        price, volume = self.prices_by_time[captured_at][symbol.symbol]
        return IntradayPriceSnapshot(
            symbol=symbol.symbol,
            market=symbol.market,
            captured_at=captured_at,
            price=Decimal(str(price)),
            volume=Decimal(str(volume)),
            source="scenario",
        )


def test_intraday_monitoring_end_to_end_scenario_returns_events_via_api(tmp_path, monkeypatch):
    db_path = str(tmp_path / "scenario.db")
    os.environ["DB_PATH"] = db_path
    import api.db.connection as api_db
    from api.main import app

    monkeypatch.setattr(api_db, "DB_PATH", db_path)
    conn = _conn(db_path)
    symbols = [
        IntradaySymbol("A", "000001", "KRX", "A", "ETF"),
        IntradaySymbol("B", "000002", "KRX", "B", "ETF"),
        IntradaySymbol("C", "000003", "KRX", "C", "ETF"),
    ]
    start = datetime(2026, 5, 27, 9, 0, tzinfo=UTC)
    later = start + timedelta(minutes=5)
    provider = ScenarioProvider(
        {
            start: {"000001": (100, 100), "000002": (100, 100), "000003": (100, 100)},
            later: {"000001": (105, 100), "000002": (95, 100), "000003": (101, 100)},
        }
    )
    config = IntradayMonitoringConfig(lookback_windows_minutes=(5,))

    first = collect_intraday_once(conn, config, provider, now=start, force=True, universe=symbols)
    second = collect_intraday_once(conn, config, provider, now=later, force=True, universe=symbols)
    events = []
    for snapshot in latest_snapshots(db_session=conn):
        events.extend(detect_events_for_snapshot(conn, snapshot, config).events)
    first_alerts = process_intraday_events(conn, events, IntradayMonitoringConfig(duplicate_suppression_minutes=10))
    duplicate_alerts = process_intraday_events(conn, events, IntradayMonitoringConfig(duplicate_suppression_minutes=10))

    with TestClient(app) as client:
        response = client.get("/api/intraday/events/recent")

    assert first.requested_symbols == 3
    assert second.inserted_snapshots == 3
    assert {event.event_type for event in events} == {"SURGE", "DROP"}
    assert first_alerts.generated_alerts == 2
    assert duplicate_alerts.suppressed_alerts == 2
    assert len(response.json()["events"]) >= 2
    assert conn.execute("SELECT COUNT(*) AS c FROM order_drafts").fetchone()["c"] == 0
    del os.environ["DB_PATH"]


def test_detector_processes_bounded_universe_fixture_without_extra_outputs(tmp_path):
    conn = _conn(tmp_path / "performance.db")
    start = datetime(2026, 5, 27, 9, 0, tzinfo=UTC)
    current_snapshots = []
    for index in range(100):
        symbol = f"{index:06d}"
        insert_snapshot(IntradayPriceSnapshot(symbol, "KRX", start, Decimal("100"), volume=Decimal("100"), source="mock"), conn)
        current_snapshots.append(
            insert_snapshot(
                IntradayPriceSnapshot(symbol, "KRX", start + timedelta(minutes=5), Decimal("101"), volume=Decimal("100"), source="mock"),
                conn,
            )
        )

    results = [detect_events_for_snapshot(conn, snapshot, IntradayMonitoringConfig(lookback_windows_minutes=(5,))) for snapshot in current_snapshots]

    assert sum(len(result.events) for result in results) == 0
    assert sum(len(result.warnings) for result in results) == 0
