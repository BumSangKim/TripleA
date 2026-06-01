from datetime import date

import api.strategy.triplea_allocator as allocator_module
from api.strategy.macro_engine import MacroRegimeDecision
from api.strategy.risk_budget_engine import RiskBudgetResult
from api.strategy.sector_tilt_engine import SectorTiltResult
from api.strategy.triplea_allocator import TripleAAllocator
from api.strategy.types import SectorBottleneckScore


def test_triplea_allocator_passes_trade_snapshot_reader_to_bottleneck_engine(monkeypatch):
    captured = {}

    class FakeBottleneckEngine:
        def __init__(self, conn, *, trade_snapshot_reader=None):
            captured["conn"] = conn
            captured["trade_snapshot_reader"] = trade_snapshot_reader

        def score(self, as_of_date):
            captured["as_of_date"] = as_of_date
            return [
                SectorBottleneckScore(
                    sector_code="SEMICONDUCTOR",
                    total_score=50.0,
                    trade_score=50.0,
                    demand_score=50.0,
                    supply_score=50.0,
                    relative_strength_score=50.0,
                    regime="inactive",
                    reasons=["fake"],
                )
            ]

    class FakeTiltEngine:
        def apply(self, weights, sector_scores, sector_assets, asset_to_bucket, *, macro_regime):
            return SectorTiltResult(adjusted_weights=weights, applied_tilts={}, reasons=["tilt"])

    class FakeRiskBudgetEngine:
        def apply(self, weights, asset_to_bucket, policy):
            return RiskBudgetResult(adjusted_weights=weights, bucket_weights={"AGGRESSIVE_ALPHA": 1.0}, violations=[], reasons=["risk"])

    monkeypatch.setattr(allocator_module, "BottleneckSectorEngine", FakeBottleneckEngine)
    monkeypatch.setattr(allocator_module, "SectorTiltEngine", lambda: FakeTiltEngine())
    monkeypatch.setattr(allocator_module, "RiskBudgetEngine", lambda: FakeRiskBudgetEngine())
    monkeypatch.setattr(
        allocator_module,
        "load_investment_universe",
        lambda universe_id: {"assets": [{"asset_code": "SMH", "bucket": "AGGRESSIVE_ALPHA", "sector": "SEMICONDUCTOR"}]},
    )
    monkeypatch.setattr(
        allocator_module,
        "load_strategy_profile",
        lambda risk_profile: {"buckets": {"AGGRESSIVE_ALPHA": {"target": 1.0, "min": 0.0, "max": 1.0}}},
    )
    monkeypatch.setattr(allocator_module, "get_sector_asset_mappings", lambda conn: {})
    reader = object()
    conn = object()

    _, _, _, _, sector_scores = TripleAAllocator(
        conn,
        trade_snapshot_reader=reader,
    )._profile_weights(
        date(2024, 3, 10),
        MacroRegimeDecision(date(2024, 3, 10), "neutral", 50, {}, []),
    )

    assert captured["conn"] is conn
    assert captured["trade_snapshot_reader"] is reader
    assert captured["as_of_date"] == date(2024, 3, 10)
    assert sector_scores[0].sector_code == "SEMICONDUCTOR"
