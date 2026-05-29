from api.brokers.kis.models import KISBalanceSnapshot, KISPosition


def test_kis_position_default_asset_class():
    pos = KISPosition(
        code="005930",
        name="삼성전자",
        quantity=2,
        avg_price=70000,
        current_price=75000,
        market_value=150000,
        profit=10000,
    )
    assert pos.asset_class == "국내주식"


def test_kis_balance_snapshot_defaults():
    snapshot = KISBalanceSnapshot(
        account_masked="12****78-01",
        total_value=200000,
        cash_value=50000,
        domestic_stock_value=150000,
        positions=[],
    )
    assert snapshot.bond_value == 0
    assert snapshot.etf_value == 0
    assert snapshot.message == ""


def test_kis_balance_snapshot_with_positions():
    positions = [
        KISPosition(
            code="005930",
            name="삼성전자",
            quantity=1,
            avg_price=70000,
            current_price=75000,
            market_value=75000,
            profit=5000,
            asset_class="국내주식",
        )
    ]
    snapshot = KISBalanceSnapshot(
        account_masked="12****78-01",
        total_value=125000,
        cash_value=50000,
        domestic_stock_value=75000,
        positions=positions,
    )
    assert len(snapshot.positions) == 1
    assert snapshot.positions[0].code == "005930"
