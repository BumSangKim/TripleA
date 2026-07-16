from pathlib import Path
from api.score_pipeline.semiconductor_subsector_scoring import compose_candidate,load_candidate
ROOT=Path(__file__).resolve().parents[3]
def test_unapproved_candidate_cannot_activate_or_increase_risk():
 c=load_candidate(ROOT/"config/parameters/semiconductor_subsector_scoring_candidates.yaml");x=compose_candidate(subsector="memory",components={"demand":1,"supply":1},candidate=c);assert x.score==.5 and x.fallback_state=="REVIEW_REQUIRED" and x.confidence==0
