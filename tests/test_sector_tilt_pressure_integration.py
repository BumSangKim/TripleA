from datetime import date

from api.strategy.adaptive_offsets import AdaptivePermissions
from api.strategy.sector_allocation_pressure import SectorAllocationPressure
from api.strategy.sector_tilt_engine import SectorTiltEngine


def test_sector_tilt_pressure_path_and_block_permission():
    weights = {"SMH": .1, "SPY": .9}
    assets = {"SEMICONDUCTOR": ["SMH"]}
    buckets = {"SMH": "AGGRESSIVE_ALPHA", "SPY": "AGGRESSIVE_ALPHA"}
    pressure = SectorAllocationPressure("SEMICONDUCTOR", date(2026, 5, 27), .9, None, None, .9, .9, .8, None, .0, None, .0, .8, .9, [])
    result = SectorTiltEngine().apply(weights, [], assets, buckets, sector_pressures=[pressure])
    blocked = SectorTiltEngine().apply(weights, [], assets, buckets, sector_pressures=[pressure], adaptive_permissions=AdaptivePermissions(sector_expansion="BLOCK"))
    assert result.adjusted_weights["SMH"] > weights["SMH"]
    assert blocked.adjusted_weights["SMH"] == weights["SMH"]
    assert result.applied_tilts["SEMICONDUCTOR"] <= .05
