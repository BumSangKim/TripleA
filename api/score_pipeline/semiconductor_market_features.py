from __future__ import annotations
from datetime import datetime
from statistics import pstdev
from api.data.market_snapshot import MarketSnapshotReader,MarketSnapshot,MarketPriceSnapshotRow
from api.plugin_boundary.contracts import FeatureValue

class SemiconductorMarketFeatureMaterializer:
 def __init__(self,reader:MarketSnapshotReader,*,base_currency:str)->None:self._r=reader;self._base=base_currency
 def materialize(self,*,asset_id:str,msci_world_id:str,semiconductor_benchmark_id:str,decision_time:datetime,snapshot_id:str)->tuple[FeatureValue,...]:
  s=self._r.read_market_snapshot(decision_time=decision_time);a=self._rows(s,asset_id);world=self._rows(s,msci_world_id);semi=self._rows(s,semiconductor_benchmark_id)
  out=[]
  for months,points in ((1,2),(3,4),(6,7),(12,13)):
   local=self._return(a,points,False,s);base=self._return(a,points,True,s);out += [self._f(f"total_return_{months}m_local",local,snapshot_id,decision_time),self._f(f"total_return_{months}m_base",base,snapshot_id,decision_time)]
  base3=self._return(a,4,True,s);out += [self._f("relative_return_msci_world_3m",self._diff(base3,self._return(world,4,True,s)),snapshot_id,decision_time),self._f("relative_return_semiconductor_benchmark_3m",self._diff(base3,self._return(semi,4,True,s)),snapshot_id,decision_time)]
  returns=[self._return(a,i,False,s) for i in range(2,min(len(a),7))];out.append(self._f("realized_volatility_adjusted_momentum",None if not returns or pstdev([x for x in returns if x is not None])==0 else (returns[-1]/pstdev([x for x in returns if x is not None])),snapshot_id,decision_time));return tuple(out)
 def _rows(self,s:MarketSnapshot,asset):return sorted([x for x in s.prices if x.asset_id==asset],key=lambda x:x.observed_at)
 def _return(self,rows,n,base,s):
  if len(rows)<n or rows[-n].price==0:return None
  start,end=rows[-n],rows[-1]
  if base:
   start_rate=self._fx(s,start.currency,start.observed_at);end_rate=self._fx(s,end.currency,end.observed_at)
   if start_rate is None or end_rate is None:return None
   return (end.price*end_rate)/(start.price*start_rate)-1
  return end.price/start.price-1
 def _fx(self,s,currency,observed):
  if currency==self._base:return 1.0
  rows=[x for x in s.fx_rates if x.base_currency==currency and x.quote_currency==self._base and x.observed_at<=observed]
  return None if not rows else sorted(rows,key=lambda x:x.observed_at)[-1].rate
 def _diff(self,a,b):return None if a is None or b is None else a-b
 def _f(self,name,value,snapshot_id,decision):
  return FeatureValue(f"semiconductor.market.{name}","asset","MARKET_INPUT",value,"ratio",decision.date(),decision,[snapshot_id],[],name,"semiconductor_market_features_v1","semiconductor_market_features_v1",1.0 if value is not None else 0.0,0 if value is not None else 1,False,["MARKET_FX_OR_PRICE_UNAVAILABLE"] if value is None else [],["MARKET_FEATURE_REVIEW_REQUIRED"] if value is None else ["MARKET_FEATURE_MATERIALIZED"],{"base_currency":self._base,"fx_contribution_traceable":True})
