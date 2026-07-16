from __future__ import annotations
from datetime import UTC,datetime
from tests.unit.score_pipeline.test_semiconductor_earnings_quality_features import ROOT,_repo
from api.score_pipeline.semiconductor_earnings_quality_features import EarningsQualityFeatureMaterializer,load_earnings_definitions
def test_company_fixture_materializes_quality_and_momentum_separately():
 out=EarningsQualityFeatureMaterializer(load_earnings_definitions(ROOT/"config/parameters/semiconductor_earnings_quality_features.yaml")).materialize(_repo(),snapshot_id="fixture",decision_time=datetime(2025,12,31,tzinfo=UTC));ids={x.feature_id for x in out};assert "semiconductor.earnings.eps_estimate_revision_1m" in ids;assert "semiconductor.earnings.balance_sheet_quality" in ids
