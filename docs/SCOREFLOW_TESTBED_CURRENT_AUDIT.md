# Scoreflow Testbed Current Audit

## 1. Current Strategy Decision Flow

The current strategy path is `MacroEngine -> TripleAAllocator -> BottleneckSectorEngine -> SectorTiltEngine -> RiskBudgetEngine -> BacktestEngine`. The flow is score-like in places, but several outputs still use labels such as macro regime and bottleneck sector regime.

## 2. Current Data Sources And DB Tables

Strategy/backtest logic uses `config/investment_universe.yaml`, `config/strategy_profiles.yaml`, `config/sector_taxonomy.yaml`, SQLite tables created by `api/db.py`, and market data tables such as `market_prices`, `fx_rates`, `indicators`, `trade_series`, `bottleneck_indicators`, and sector maps.

## 3. Current Macro Logic

`api/strategy/macro_engine.py` evaluates current macro indicators and produces a score/regime label. It is not yet a full distribution-style response input.

## 4. Current Bottleneck Sector Logic

`api/strategy/bottleneck_sector_engine.py` scores sector trade, demand, supply, and relative-strength signals. It is sector-specific but currently sits as a direct engine rather than a plugin.

## 5. Current Sector Tilt Logic

`api/strategy/sector_tilt_engine.py` applies tilts from bottleneck regimes such as active/emerging. It does not yet use continuous allocation pressure.

## 6. Current Risk Budget Logic

`api/strategy/risk_budget_engine.py` clamps asset weights to bucket min/max rules from strategy profiles. Hard account constraints are separate in `api/strategy/account_constraints`.

## 7. Current Backtest Logic

`api/backtest_engine.py` runs periodic target allocation simulation using historical prices, FX, fees, and slippage. It does not yet store score-flow testbed decisions by default.

## 8. Current Order Candidate Logic

Order draft/candidate behavior exists in service/API modules, but live execution remains disabled by policy. This audit does not change order behavior.

## 9. Current Test Coverage

Existing tests cover API endpoints, macro/risk/sector engines, backtest behavior, account constraints, Phase Pre-3 universe/data modules, and Phase 3 raw data pipeline.

## 10. Gaps Versus Target Score-Flow Testbed

- Common score contract for all score-flow outputs.
- Feature/score/decision/experiment store schema.
- Observation universe separate from investable universe.
- Specialized indicator plugin registry.
- Bottleneck plugin migration.
- Continuous sector allocation pressure.
- Macro distribution and state features.
- Unified regime response and adaptive offsets.
- Judgment backtest, recursive optimization, robustness, and reporting.

## 11. Risks For Future Refactors

- Existing labels must remain backward-compatible while new continuous outputs are introduced.
- Bottleneck data must not become the universal sector model.
- Optimization must not auto-promote parameters or optimize for return alone.
- Hard constraints must remain final filters after adaptive offsets.

## 12. Files Likely To Change Later

- `api/strategy/*`
- `api/backtest_engine.py`
- `api/services.py`
- `api/db.py`
- `config/*.yaml`
- `tests/`
