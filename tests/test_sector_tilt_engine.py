from api.strategy.sector_tilt_engine import SectorTiltEngine
from api.strategy.types import SectorBottleneckScore


def test_sector_tilt_engine_adds_active_sector_satellite_weight():
    result = SectorTiltEngine().apply(
        asset_weights={
            "SPY": 0.225,
            "QQQ": 0.225,
            "TLT": 0.20,
            "GOLD": 0.20,
            "CASH_KRW": 0.15,
        },
        sector_scores=[
            SectorBottleneckScore(
                sector_code="SEMICONDUCTOR",
                total_score=78.0,
                trade_score=80.0,
                demand_score=50.0,
                supply_score=50.0,
                relative_strength_score=85.0,
                regime="active",
                reasons=[],
            )
        ],
        sector_assets={"SEMICONDUCTOR": ["SMH"]},
        asset_to_bucket={
            "SPY": "AGGRESSIVE_ALPHA",
            "QQQ": "AGGRESSIVE_ALPHA",
            "SMH": "AGGRESSIVE_ALPHA",
            "TLT": "DEFENSIVE_CORE",
            "GOLD": "DEFENSIVE_CORE",
            "CASH_KRW": "LIQUIDITY",
        },
    )

    assert round(result.adjusted_weights["SMH"], 6) == 0.05
    assert result.adjusted_weights["SPY"] < 0.225
    assert result.applied_tilts["SEMICONDUCTOR"] == 0.05


def test_sector_tilt_engine_reduces_tilt_in_risk_off():
    result = SectorTiltEngine().apply(
        asset_weights={"SPY": 0.45, "SMH": 0.0, "TLT": 0.40, "CASH_KRW": 0.15},
        sector_scores=[
            SectorBottleneckScore(
                sector_code="SEMICONDUCTOR",
                total_score=78.0,
                trade_score=80.0,
                demand_score=50.0,
                supply_score=50.0,
                relative_strength_score=85.0,
                regime="active",
                reasons=[],
            )
        ],
        sector_assets={"SEMICONDUCTOR": ["SMH"]},
        asset_to_bucket={
            "SPY": "AGGRESSIVE_ALPHA",
            "SMH": "AGGRESSIVE_ALPHA",
            "TLT": "DEFENSIVE_CORE",
            "CASH_KRW": "LIQUIDITY",
        },
        macro_regime="risk_off",
    )

    assert round(result.adjusted_weights["SMH"], 6) == 0.025
