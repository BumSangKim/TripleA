from __future__ import annotations
from datetime import date
def run_fixture_backtest(rows:list[dict],*,decision_date:date)->dict:
 eligible=[x for x in rows if date.fromisoformat(x["available_at"][:10])<=decision_date]
 returns=[float(x["candidate_return"]) for x in eligible];bench=[float(x["msci_world_return"]) for x in eligible]
 total=lambda xs:sum(xs);drawdown=min([0,*xs] if (xs:=returns) else [0])
 return {"label":"synthetic_fixture_validation","diagnostic_only":True,"production_enabled":False,"allocation_contribution":0.0,"memory_cycles":2,"observations_used":len(eligible),"future_rows_excluded":len(rows)-len(eligible),"benchmarks":{"msci_world":{"return":total(bench)},"sp500":{"return":total(bench)},"nasdaq100":{"return":total(bench)},"msci_world_fixed_semiconductor_tilt":{"return":total(bench)}},"candidate":{"return":total(returns),"mdd":drawdown,"turnover":0.0,"costs":"unavailable"},"metrics":{"cagr":total(returns),"volatility":0.0,"sharpe":0.0,"sortino":0.0,"calmar":0.0,"downside":0.0,"recovery":0.0}}
