from __future__ import annotations
from datetime import UTC,date,datetime,timedelta
from api.data.market_snapshot import FixtureMarketSnapshotReader,MarketPriceSnapshotRow,FxSnapshotRow
from api.score_pipeline.semiconductor_market_features import SemiconductorMarketFeatureMaterializer
def test_market_snapshot_excludes_future_fx_and_marks_base_return_unavailable():
 t=datetime(2025,12,31,tzinfo=UTC);p=tuple(MarketPriceSnapshotRow(x,date(2025+i//12,i%12+1,1),t,100+i,"USD","fixture",t.date()) for x in ("ASSET","WORLD","SEMI") for i in range(13));future=FxSnapshotRow("USD","KRW",date(2025,1,1),t+timedelta(days=1),1300,"fixture",t.date());out=SemiconductorMarketFeatureMaterializer(FixtureMarketSnapshotReader(p,(future,)),base_currency="KRW").materialize(asset_id="ASSET",msci_world_id="WORLD",semiconductor_benchmark_id="SEMI",decision_time=t,snapshot_id="fixture");assert next(x for x in out if x.feature_id.endswith("total_return_3m_local")).feature_value is not None;assert next(x for x in out if x.feature_id.endswith("total_return_3m_base")).feature_value is None
