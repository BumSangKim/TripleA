# AI Capex-Token Scoring Integration Plan

Task: `001_inspect_ai_capex_token_architecture_boundaries`

This document records the current repository boundaries before implementing the
AI Capex-Token scoring slice. It is an integration plan only; no strategy,
allocation, rebalancing, order candidate, broker, KIS, or execution behavior is
activated by this task.

## Current Repository Evidence

- Root guide: `MASTER_DEVELOPMENT_GUIDE.md`.
- Progress/status: `DevelopPlans/STATUS.md`.
- Existing score helper contract: `api/strategy/score_contract.py`.
- Existing score-pipeline contract set: `api/score_pipeline/contracts.py`.
- Existing sector engines:
  - `api/strategy/common_sector_scoring_engine.py`
  - `api/strategy/sector_tilt_engine.py`
- Plugin boundary files:
  - `api/plugin_boundary/contracts.py`
  - `api/plugin_boundary/input_resolver.py`
  - `api/plugin_boundary/time_guard.py`
- Existing scoring config conventions:
  - `config/parameters/ai_capex_cycle.yaml`
  - `config/parameters/bio_capex_bottleneck.yaml`
  - `config/parameters/sectors.yaml`
  - `config/sector_scoring.yaml`
  - `config/score_definitions*.yaml`
- Existing test roots:
  - `tests/unit/strategy/`
  - `tests/integration/pipeline/`
  - `tests/backtest/`
  - `tests/architecture/`

## Important Structure Finding

`api/domain/scoring/` does not exist yet. Task 002 in this package explicitly
creates `api/domain/scoring/ai_capex_token_contracts.py` and
`api/domain/scoring/__init__.py`, so the integration path should treat this as a
new pure-domain contract location rather than a broad architecture move.

The current score contract location is still clear:

- `api/strategy/score_contract.py` provides `ScoreComponent`, `ScoreSignal`,
  `clamp_score`, `safe_weighted_average`, `confidence_adjusted_score`, and
  `combine_reason_codes`.
- `api/score_pipeline/contracts.py` provides broader score-pipeline output
  contracts and conservative action definitions.

## Plugin And Time-Availability Boundary

`api/plugin_boundary/time_guard.py` exposes:

- `is_available_for_decision(value, decision_time)`
- `filter_available_values(values, decision_time)`

The helper requires every value to have `available_at` and returns only values
where `available_at <= decision_time`. This is clear enough for point-in-time
availability checks in later input adapter and leakage tests.

## Sector Integration Point

`api/strategy/common_sector_scoring_engine.py` currently produces a
`CommonSectorScore` from price history and static component weights. It does not
expose a general plugin component registry. Therefore AI Capex-Token sector
work should start as a diagnostic/component output and integrate with the
existing sector scoring engine only if a later task confirms a narrow, safe
extension point.

`api/strategy/sector_tilt_engine.py` applies sector scores to weights. It is not
a safe integration point for this package because the package must not alter
allocation, rebalancing, or active target-weight behavior.

## Planned Implementation Path

1. Add pure domain contracts under `api/domain/scoring/`.
2. Add parameter metadata under `config/scoring/` with `approved: false` until
   explicitly approved.
3. Add explicit fixtures under `tests/fixtures/ai_capex_token/`.
4. Add a plugin-boundary input adapter that uses explicit `period_role` and
   `available_at` checks.
5. Build features and scenario distribution from explicit fixture/input values.
6. Add sector component and macro overlay outputs as score components, not as
   buy/sell/order instructions.
7. Integrate with sector scoring only as diagnostic/component extension unless
   a safe extension point is proven.
8. Add input-to-score, no-lookahead, architecture, and audit reason-code tests.

## Conservative Fallbacks

Use only these fallback states when inputs are missing, stale, unavailable at
decision time, or semantically unclear:

- `NO_ACTION`
- `HOLD`
- `REVIEW_REQUIRED`
- `RISK_REDUCE_ONLY`

No fallback may increase risk, change target weights, submit orders, or activate
broker/KIS behavior.

## Stop Conditions

Stop before implementation if any later task requires:

- new production parameter defaults without explicit metadata and approval;
- inferring current/previous values from source suffixes, list order, or metric
  key suffixes instead of explicit period roles;
- threshold-switch investment action from scenario labels;
- changing macro thresholds, allocation defaults, sector tilt behavior,
  rebalancing behavior, order candidate behavior, or public API defaults;
- direct imports from domain contracts to FastAPI, SQLite, `api.db`,
  `api.features`, broker/KIS, or execution paths;
- broad architecture directory movement or compatibility shims.
