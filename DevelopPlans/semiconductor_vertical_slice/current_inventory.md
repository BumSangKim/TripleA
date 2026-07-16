# SEM-001 Current Inventory

## Scope and evidence

This inventory is evidence-based and does not activate semiconductor strategy
behavior. The canonical pipeline is
`config/pipelines/investment_decision.yaml`, validated by
`api.score_pipeline.pipeline_manifest.validate_pipeline_manifest`.

The current pipeline already orders data, features, scores, macro, sector and
asset scoring, risk budget, allocation, rebalancing, hard constraints,
simulation output, and audit. It also sets `auto_execution_allowed: false`.

## Current capabilities

| Stage | Status | Current evidence | Boundary note |
|---|---|---|---|
| Asset universe and IDs | READY | `config/universe/asset_master.yml`; `config/universe/universe_selectors.yml`; `api/universe/loader.py` | Semiconductor ETF and reference assets already use canonical `asset_id`, feature, role, tradability, and data-requirement metadata. |
| Raw point-in-time data | EXTEND | `api/data/capex_models.py`; `api/data/capex_ports.py`; `api/data/capex_snapshot_builder.py` | Generic time-series and company-metric points carry `available_at`, `updated_at`, revision, source, and confidence. Semiconductor metric catalog/owners are absent. |
| Data quality and snapshots | READY | `api/score_pipeline/data_quality.py`; `api/data/capex_feature_materializer.py` | `SnapshotBuilder` rejects future points; capex materialization preserves snapshot metadata. |
| AI CAPEX / token input | PARTIAL | `api/domain/scoring/ai_capex_token_contracts.py`; `api/strategy/ai_capex_token_input_adapter.py`; `api/strategy/ai_capex_token_features.py` | Existing contract covers token and capex directions only, not the full semiconductor supply chain. |
| AI CAPEX diagnostic components | PARTIAL | `api/strategy/ai_capex_token_component.py`; `api/strategy/ai_capex_token_sector_components.py`; `api/strategy/ai_capex_token_macro_overlay.py` | Components are explicitly diagnostic-only and `applied_to_sector_engine=False`. |
| Memory-cycle coverage | PARTIAL | `api/score_pipeline/memory_cycle.py`; `api/features/backtests/ai_capex_token_memory_cycle_gate.py` | Cycle coverage exists for diagnostics; it is not a semiconductor feature contract. |
| Market/sector scoring | PARTIAL | `api/strategy/common_sector_scoring_engine.py`; `api/strategy/sector_score_aggregator.py` | Common score and price-history path exists. No semiconductor subsector score contract exists. |
| Macro/risk | PARTIAL | `api/strategy/macro_distribution.py`; `api/strategy/risk_budget_engine.py`; `api/strategy/account_constraints/engine.py` | Reusable macro distribution, risk-budget, and hard-constraint boundaries exist. Current active formulas must remain unchanged. |
| Allocation/rebalancing | PARTIAL | `api/strategy/sector_tilt_engine.py`; `api/strategy/allocation_offsets.py`; `api/features/rebalancing/service.py` | Existing behavior is active-path legacy/current behavior; semiconductor slice must not wire into it without a later approved task. |
| Backtest/audit | PARTIAL | `api/score_pipeline/backtest.py`; `api/features/backtests/service.py`; `api/features/backtests/ports.py`; `tests/backtest/test_ai_capex_token_future_data_leakage.py` | Deterministic and no-lookahead tests exist, but no full semiconductor vertical-slice point-in-time backtest exists. |
| Tuning/shadow evidence | READY | `config/parameters/ai_capex_token_adaptive_selected_candidate.yaml`; `reports/backtest/ai_capex_token_adaptive/final_validation_summary.md` | Existing selected candidate is `diagnostic_only`, `production_enabled: false`, and allocation contribution is `0.0`. |
| MSCI World core / look-through | MISSING | `config/backtests/sector_component_sector_portfolios.yaml` has generic look-through controls | No canonical MSCI World benchmark identifier, point-in-time holdings dataset, or semiconductor overlap computation was found. |

## Semiconductor universe evidence

- `KRX_396500` and `KRX_381180` are semiconductor ETF assets with
  `enabled_state: disabled_until_backtested`.
- `KRX_005930`, `KRX_000660`, and `US_NVDA` are monitor-only scoring
  references with semiconductor-related features and strategy roles.
- `semiconductor_scoring_references` resolves feature-tagged references.
- `semiconductor_order_candidates` exists in the selector file, but SEM-001
  does not use or activate it.

## Existing guardrails

- `api/score_pipeline/pipeline_manifest.py` requires hard constraints before
  simulation output and rejects automatic execution.
- `api/score_pipeline/data_quality.HistoricalSnapshot.get_available` and
  `SnapshotBuilder.build` enforce decision-time availability.
- `api/strategy/ai_capex_token_input_adapter.AICapexTokenInputAdapter` filters
  unavailable inputs through `api.plugin_boundary.time_guard`.
- `tests/architecture/` and `tests/integration/pipeline/` provide the current
  architecture and deterministic pipeline regression suites.

## Explicit non-activation finding

No existing semiconductor artifact identified here may alter allocation,
rebalancing, order candidates, execution, or real-account behavior. The
current AI CAPEX-Token selected candidate remains shadow-only.
