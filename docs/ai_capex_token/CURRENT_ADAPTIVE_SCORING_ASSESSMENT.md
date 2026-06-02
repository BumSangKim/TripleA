# Current Adaptive Scoring Assessment

Task: `001_confirm_current_scoring_adaptiveness_and_boundaries`

Status: current scoring is partially adaptive, but AI Capex-Token tuning is not
yet market-adaptive enough for return-oriented tuning. Production remains
disabled and diagnostic/shadow-only.

## 1. Current Adaptive Elements

- `api/score_pipeline/scoring.py` provides score flow with:
  - normalized score;
  - EMA smoothing through `ema_smooth`;
  - `previous_score`;
  - `score_change`;
  - confidence adjustment;
  - data-quality adjustment;
  - stability;
  - adjustment intensity;
  - parameter and model version fields.
- `api/score_pipeline/data_quality.py` provides:
  - `HistoricalSnapshot.get_available`;
  - future-data rejection when `available_at.date() > decision_date`;
  - `DataQualityAssessor`;
  - conservative quality actions for stale, missing, or low-quality inputs.
- `api/score_pipeline/parameters.py` provides a versioned
  `ParameterRegistry`. Inactive or unapproved parameters return conservative
  fallback metadata instead of silently becoming production defaults.
- `api/score_pipeline/backtest.py` has a deterministic pipeline backtest runner
  with simulation dates, transaction-cost hooks, decision logs, metrics, and
  warnings.
- `api/backtest_engine.py` is reached through a service/runner boundary under
  `api/features/backtests/service.py`, preserving the local simulation posture.
- `config/parameters/default.yaml` stores core score-flow parameters as data,
  including `ema_span`, `target_change_limit`, `transaction_cost_bps`, and
  account risk limits.
- `config/scoring/ai_capex_token.yaml` keeps AI Capex-Token diagnostic gates
  closed: `enabled: false`, `production_enabled: false`, `diagnostic_only:
  true`, and `approved: false`.
- Existing AI Capex-Token tests cover explicit fixtures, input adapter
  availability filtering, feature building, scenario distribution, diagnostic
  sector components, macro overlay, input-to-score flow, future-data leakage,
  architecture boundaries, and UI diagnostic output.

## 2. Current Static Or Non-Adaptive Elements

- `api/score_pipeline/plugins/ai_capex_cycle.py` uses `ai_cycle_weights` from
  `config/parameters/ai_capex_cycle.yaml`. The values are parameterized, but
  they are not fitted from a leakage-safe historical calibration window.
- `api/score_pipeline/plugins/capex_common.py` exposes `score_from_z` with
  static `center=0.5` and `scale=0.2` defaults.
- `config/parameters/ai_capex_cycle.yaml` contains static
  `normalization_bounds`. They are staged and unapproved, but not adaptive to
  market state.
- `api/score_pipeline/engines.py` contains fixed coefficients in macro, sector,
  risk, allocation, and rebalancing logic. These are current baseline behavior
  and must not be changed by adaptive AI Capex-Token tuning without explicit
  task scope and tests.
- `api/score_pipeline/plugins/capex_scenario.py` uses a continuous
  distribution, but it is not the requested S1-S9 token-delta by
  capex-acceleration grid for adaptive AI Capex-Token tuning.
- Existing AI Capex-Token diagnostic sector components are continuous and
  explanation-only, but their current test config uses explicit test values
  rather than adaptive rolling calibration.
- Direct label-to-weight risks are guarded by tests, but future tuning still
  needs tests proving dominant scenario labels do not become fixed weights,
  orders, or buy/sell switches.

## 3. Required Changes Before Tuning

Before optimizing any return metric:

- add an adaptive scoring contract with traceable calibration metadata;
- add a two-complete-memory-cycle coverage gate and stop if coverage is not
  proven from available local/fixture data;
- validate the path from deterministic input collection or repository boundary
  to score/backtest output;
- implement or verify leakage-safe adaptive normalization using only data
  available at the simulated decision date;
- implement S1-S9 scenario probabilities as a distribution, not a hard label;
- keep sector components diagnostic-only until a safe integration point is
  explicitly approved;
- add no-fixed-market-value and no-label-to-action tests;
- keep production disabled and shadow/diagnostic-only.

## 4. Existing Commands For Tests And Backtests

Discovered commands for this repo:

```bash
git diff --check
.venv/bin/python -m pytest -q --collect-only
.venv/bin/python -m pytest tests/architecture -q
.venv/bin/python -m pytest tests/unit/strategy -q
.venv/bin/python -m pytest tests/integration/strategy -q
.venv/bin/python -m pytest tests/backtest -q
```

The collect-only command for this task is:

```bash
.venv/bin/python -m pytest -q --collect-only
```

The shell command `python` is not assumed to exist in this environment; use
`.venv/bin/python` for repo validation.

## 5. Existing Extension Points

- Domain contracts: `api/domain/scoring/ai_capex_token_contracts.py`.
- Diagnostic AI Capex-Token modules:
  - `api/strategy/ai_capex_token_input_adapter.py`
  - `api/strategy/ai_capex_token_features.py`
  - `api/strategy/ai_capex_token_scenario_engine.py`
  - `api/strategy/ai_capex_token_sector_components.py`
  - `api/strategy/ai_capex_token_macro_overlay.py`
  - `api/strategy/ai_capex_token_component.py`
- Score-pipeline primitives:
  - `api/score_pipeline/contracts.py`
  - `api/score_pipeline/scoring.py`
  - `api/score_pipeline/data_quality.py`
  - `api/score_pipeline/parameters.py`
  - `api/score_pipeline/backtest.py`
- Backtest UI diagnostic endpoint:
  - `api/features/backtests/ai_capex_token_diagnostic.py`
  - `web/app/backtests/AICapexTokenDiagnosticPanel.tsx`
- Architecture tests:
  - `tests/architecture/test_ai_capex_token_boundaries.py`
  - broader `tests/architecture/` suite.

## Boundary Verdict

`001` may proceed because the scoring and backtest boundaries are discoverable.
However, later tuning must stop with `INSUFFICIENT_MEMORY_CYCLE_COVERAGE` if
two complete memory cycles cannot be proven, and with
`ARCHITECTURE_BOUNDARY_UNRESOLVED` if a task requires changing allocation,
rebalancing, order-candidate, broker, KIS, or execution behavior.
