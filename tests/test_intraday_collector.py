import sqlite3
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from api.features.intraday.collector import collect_intraday_once, is_regular_session
from api.features.intraday.config import IntradayMonitoringConfig
from api.features.intraday.provider import MockIntradayProvider
from api.features.intraday.repository import latest_snapshot
from api.features.intraday.universe import IntradaySymbol, resolve_intraday_universe


def _conn(tmp_path):
    conn = sqlite3.connect(tmp_path / "intraday.db")
    conn.row_factory = sqlite3.Row
    return conn


def _symbols():
    return [
        IntradaySymbol("KRX_360750", "360750", "KRX", "TIGER", "ETF"),
        IntradaySymbol("KRX_005930", "005930", "KRX", "Samsung", "STOCK"),
    ]


def test_collector_resolves_investable_symbols_from_universe():
    symbols = resolve_intraday_universe(IntradayMonitoringConfig(provider="mock"))

    assert symbols
    assert {"360750", "005930"}.issubset({symbol.symbol for symbol in symbols})


def test_regular_session_checker_uses_configured_full_session():
    config = IntradayMonitoringConfig()
    kst = ZoneInfo("Asia/Seoul")

    assert is_regular_session(datetime(2026, 5, 27, 9, 0, tzinfo=kst), config) is True
    assert is_regular_session(datetime(2026, 5, 27, 15, 30, tzinfo=kst), config) is True
    assert is_regular_session(datetime(2026, 5, 27, 15, 31, tzinfo=kst), config) is False


def test_collector_calls_provider_and_persists_successful_snapshots(tmp_path):
    conn = _conn(tmp_path)
    provider = MockIntradayProvider()
    now = datetime(2026, 5, 27, 9, 1, tzinfo=UTC)

    result = collect_intraday_once(conn, IntradayMonitoringConfig(), provider, now=now, force=True, universe=_symbols())

    assert provider.requested == ["360750", "005930"]
    assert result.requested_symbols == 2
    assert result.successful_symbols == 2
    assert result.inserted_snapshots == 2
    assert latest_snapshot(symbol="360750", market="KRX", db_session=conn) is not None


def test_collector_records_per_symbol_failures_without_aborting(tmp_path):
    conn = _conn(tmp_path)
    provider = MockIntradayProvider(fail_symbols={"005930"})

    result = collect_intraday_once(
        conn,
        IntradayMonitoringConfig(),
        provider,
        now=datetime(2026, 5, 27, 9, 1, tzinfo=UTC),
        force=True,
        universe=_symbols(),
    )

    assert result.successful_symbols == 1
    assert result.failed_symbols == 1
    assert result.inserted_snapshots == 1
    assert result.warnings[0].symbol == "005930"
    assert result.warnings[0].reason_code == "PROVIDER_ERROR"


def test_disabled_config_returns_no_op(tmp_path):
    result = collect_intraday_once(
        _conn(tmp_path),
        IntradayMonitoringConfig(enabled=False),
        MockIntradayProvider(),
        now=datetime(2026, 5, 27, 9, 1, tzinfo=UTC),
        force=True,
    )

    assert result.status == "no_op"
    assert result.requested_symbols == 0
    assert result.warnings[0].reason_code == "DISABLED"


def test_outside_market_session_returns_no_op_unless_forced(tmp_path):
    conn = _conn(tmp_path)
    now = datetime(2026, 5, 27, 23, 0, tzinfo=UTC)

    result = collect_intraday_once(conn, IntradayMonitoringConfig(), MockIntradayProvider(), now=now, universe=_symbols())
    forced = collect_intraday_once(conn, IntradayMonitoringConfig(), MockIntradayProvider(), now=now, force=True, universe=_symbols())

    assert result.status == "no_op"
    assert result.warnings[0].reason_code == "OUTSIDE_MARKET_SESSION"
    assert forced.inserted_snapshots == 2


def test_provider_payload_normalization_and_stale_warning(tmp_path):
    conn = _conn(tmp_path)
    provider = MockIntradayProvider(stale_symbols={"360750"})

    result = collect_intraday_once(
        conn,
        IntradayMonitoringConfig(stale_data_tolerance_seconds=120),
        provider,
        now=datetime(2026, 5, 27, 9, 1, tzinfo=UTC),
        force=True,
        universe=_symbols()[:1],
    )
    saved = latest_snapshot(symbol="360750", market="KRX", db_session=conn)

    assert result.inserted_snapshots == 1
    assert result.warnings[0].reason_code == "STALE_DATA"
    assert saved is not None
    assert saved.source == "mock"
    assert saved.is_stale is True
    assert saved.quality_score == 0.5


def test_invalid_provider_data_warns_and_is_not_inserted(tmp_path):
    conn = _conn(tmp_path)
    provider = MockIntradayProvider(invalid_symbols={"360750"})

    result = collect_intraday_once(
        conn,
        IntradayMonitoringConfig(),
        provider,
        now=datetime(2026, 5, 27, 9, 1, tzinfo=UTC),
        force=True,
        universe=_symbols()[:1],
    )

    assert result.failed_symbols == 1
    assert result.inserted_snapshots == 0
    assert result.warnings[0].reason_code == "INVALID_PRICE"
