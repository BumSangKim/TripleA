import sqlite3

import pytest
import requests

from api import db as api_db
from api.kis import (
    KISBalanceSnapshot,
    KISClient,
    KISConfig,
    KISNetworkError,
    KISPosition,
    load_kis_config,
    parse_domestic_balance,
)
from api.providers import ProviderRouter


def test_load_kis_config_prefers_demo_credentials():
    config = load_kis_config(
        {
            "KIS_ISDEMO": "true",
            "KIS_APP_KEY": "real_key",
            "KIS_APP_SECRET": "real_secret",
            "KIS_DEMO_APP_KEY": "demo_key",
            "KIS_DEMO_APP_SECRET": "demo_secret",
            "KIS_ACCOUNT_NO": "12345678-01",
            "KIS_ACCOUNT_TYPE": "ISA",
            "KIS_ACCOUNT_NAME": "Demo ISA",
        },
        force_demo=True,
    )

    assert config.is_demo is True
    assert config.app_key == "demo_key"
    assert config.app_secret == "demo_secret"
    assert config.cano == "12345678"
    assert config.account_product_code == "01"
    assert config.account_type == "ISA"
    assert config.account_name == "Demo ISA"


def test_parse_domestic_balance_normalizes_positions():
    config = KISConfig(
        app_key="key",
        app_secret="secret",
        cano="12345678",
        account_product_code="01",
        is_demo=True,
    )
    data = {
        "rt_cd": "0",
        "msg1": "정상처리",
        "output1": [
            {
                "pdno": "005930",
                "prdt_name": "삼성전자",
                "hldg_qty": "2",
                "pchs_avg_pric": "70000",
                "prpr": "75000",
                "evlu_amt": "150000",
                "evlu_pfls_amt": "10000",
            },
            {"pdno": "000000", "hldg_qty": "0", "evlu_amt": "0"},
        ],
        "output2": [{"dnca_tot_amt": "50000", "tot_evlu_amt": "200000"}],
    }

    snapshot = parse_domestic_balance(data, config)

    assert snapshot.account_masked == "12****78-01"
    assert snapshot.total_value == 200000
    assert snapshot.cash_value == 50000
    assert snapshot.domestic_stock_value == 150000
    assert len(snapshot.positions) == 1
    assert snapshot.positions[0].code == "005930"


def test_kis_client_masks_network_errors():
    config = KISConfig(
        app_key="key",
        app_secret="secret",
        cano="12345678",
        account_product_code="01",
        is_demo=True,
    )

    class FailingSession:
        def post(self, *args, **kwargs):
            raise requests.Timeout("request timed out")

    with pytest.raises(KISNetworkError) as exc:
        KISClient(config, session=FailingSession()).issue_token()

    assert "KIS token request failed" in str(exc.value)


def test_paper_provider_syncs_kis_snapshot(tmp_path, monkeypatch):
    db_path = str(tmp_path / "dashboard.db")
    monkeypatch.setattr(api_db, "DB_PATH", db_path)
    api_db.ensure_dashboard_tables()

    snapshot = KISBalanceSnapshot(
        account_masked="12****78-01",
        total_value=250000,
        cash_value=50000,
        domestic_stock_value=200000,
        message="정상처리",
        positions=[
            KISPosition(
                code="005930",
                name="삼성전자",
                quantity=2,
                avg_price=70000,
                current_price=100000,
                market_value=200000,
                profit=60000,
            )
        ],
    )

    def fake_load_kis_config(*, force_demo=None):
        assert force_demo is True
        return KISConfig(
            app_key="demo_key",
            app_secret="demo_secret",
            cano="12345678",
            account_product_code="01",
            is_demo=True,
            account_type="ISA",
            account_name="Demo ISA",
        )

    class FakeKISClient:
        def __init__(self, config):
            self.config = config

        def fetch_domestic_balance(self):
            return snapshot

    monkeypatch.setattr("api.providers.load_kis_config", fake_load_kis_config)
    monkeypatch.setattr("api.providers.KISClient", FakeKISClient)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    result = ProviderRouter().get("paper").sync_accounts(conn)

    assert result.ok is True
    assert result.accountMasked == "12****78-01"
    assert result.syncedPositions == 1

    account = conn.execute("SELECT * FROM accounts WHERE id=?", (result.accountId,)).fetchone()
    assert account["name"] == "Demo ISA"
    assert account["account_type"] == "ISA"
    assert account["connection_status"] == "CONNECTED"
    assert account["data_source"] == "KIS_PAPER"
    assert account["trade_status"] == "PAPER_READ_ONLY"

    holding = conn.execute("SELECT * FROM holdings WHERE account_id=?", (result.accountId,)).fetchone()
    assert holding["ticker"] == "005930"
    assert holding["market_value"] == 200000
    assert holding["strategy_bucket"] == "BROKER_SYNC"

    saved_snapshot = conn.execute(
        "SELECT * FROM account_snapshots WHERE account_id=?",
        (result.accountId,),
    ).fetchone()
    assert saved_snapshot["total_value"] == 250000
    assert saved_snapshot["cash_value"] == 50000
