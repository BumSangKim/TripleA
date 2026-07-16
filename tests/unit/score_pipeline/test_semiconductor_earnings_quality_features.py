from __future__ import annotations
from datetime import UTC,datetime
from decimal import Decimal
from pathlib import Path
import pytest
from api.data.adapters.semiconductor_fixtures import FixtureSemiconductorObservationRepository
from api.domain.semiconductor_observations import SemiconductorDataQuality,SemiconductorObservation
from api.score_pipeline.semiconductor_earnings_quality_features import EarningsQualityFeatureMaterializer,load_earnings_definitions
ROOT=Path(__file__).resolve().parents[3]
def test_earnings_revisions_are_release_aware_and_missing_estimates_fallback():
 d=load_earnings_definitions(ROOT/"config/parameters/semiconductor_earnings_quality_features.yaml");out=EarningsQualityFeatureMaterializer(d).materialize(_repo(),snapshot_id="fixture",decision_time=datetime(2025,12,31,tzinfo=UTC));eps=next(x for x in out if x.entity_id=="US_NVDA" and x.feature_id.endswith("eps_estimate_revision_1m"));assert eps.feature_value==pytest.approx(0.1);missing=next(x for x in out if x.entity_id=="KRX_005930" and x.feature_id.endswith("eps_estimate_revision_1m"));assert missing.feature_value is None and missing.data_quality==0
def _repo():
 rows=[]
 for c in ("US_NVDA","KRX_005930"):
  for metric in ("revenue_estimate","margin","fcf_margin","roic","balance_sheet_quality","earnings"):
   rows+=_rows(c,metric,[1,1.1,1.2,1.3])
 rows+=_rows("US_NVDA","eps_estimate",[1,1.1,1.2,1.32]);return FixtureSemiconductorObservationRepository(rows)
def _rows(c,m,vals):
 return [SemiconductorObservation(f"semiconductor.company.{c}.{m}.monthly",Decimal(str(v)),datetime(2025,i+1,1).date(),datetime(2025,12,1,tzinfo=UTC),datetime(2025,12,1,tzinfo=UTC),datetime(2025,12,1,tzinfo=UTC),"fixture",str(i),str(i),"monthly","ratio",SemiconductorDataQuality(1,False,False)) for i,v in enumerate(vals)]
