from datetime import date
from api.score_pipeline.semiconductor_fixture_backtest import run_fixture_backtest
def test_synthetic_two_cycle_backtest_is_deterministic_and_excludes_future_rows():
 rows=[{"available_at":"2025-01-01","candidate_return":.01,"msci_world_return":.005},{"available_at":"2025-02-01","candidate_return":-.01,"msci_world_return":-.005},{"available_at":"2026-01-01","candidate_return":1,"msci_world_return":1}];a=run_fixture_backtest(rows,decision_date=date(2025,12,31));assert a==run_fixture_backtest(rows,decision_date=date(2025,12,31));assert a["memory_cycles"]==2 and a["future_rows_excluded"]==1 and a["allocation_contribution"]==0
