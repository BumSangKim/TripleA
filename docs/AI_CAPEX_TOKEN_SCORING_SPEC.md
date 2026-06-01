# AI Capex-Token Scoring Spec

Status: diagnostic-only draft.

This spec documents the implemented AI Capex-Token component. It is not a
production trading rule and does not activate allocation, rebalancing, order
candidate, broker, KIS, or execution behavior.

## Scope

In scope:

- explicit AI token consumption and AI capex inputs;
- point-in-time filtering by `available_at <= decision_date end-of-day`;
- feature values for token consumption change, capex growth, and capex
  acceleration;
- S1-S9 scenario probability distribution;
- diagnostic sector component outputs;
- macro overlay that adjusts confidence metadata only;
- conservative fallback and audit reason codes.

Out of scope:

- live account control;
- order creation or submission;
- fixed target weights from scenario labels;
- production parameter approval;
- changes to macro thresholds, allocation, rebalancing, or sector tilt behavior.

## Implemented Files

- `api/domain/scoring/ai_capex_token_contracts.py`
- `api/strategy/ai_capex_token_input_adapter.py`
- `api/strategy/ai_capex_token_features.py`
- `api/strategy/ai_capex_token_scenario_engine.py`
- `api/strategy/ai_capex_token_sector_components.py`
- `api/strategy/ai_capex_token_macro_overlay.py`
- `api/strategy/ai_capex_token_component.py`
- `config/scoring/ai_capex_token.yaml`

## Input Schema

The adapter accepts a mapping or plugin-style object with `.data`. Required
top-level fields are:

- `snapshot_id`
- `decision_date`
- `token_sources_current`
- `token_sources_previous`
- `capex_series`
- `sector_metrics`
- `macro_overlay_metrics`

Each metric row requires:

- `metric_key`
- `period_role`
- `value`
- `as_of_date`
- `available_at`
- `source`
- `quality_score`
- `missing_ratio`
- `is_stale`

Token period roles are explicit: `current`, `previous`.
Capex period roles are explicit: `t`, `t_minus_1`, `t_minus_2`.

The adapter does not infer period roles from source names, metric keys, or list
order.

## Point-In-Time Rule

Decision time is derived as end-of-day for `decision_date`. A metric is eligible
only when:

```text
metric.available_at <= decision_date 23:59:59
```

Future rows are excluded before feature construction. If required current or
capex rows are unavailable after filtering, the adapter returns or raises
`REVIEW_REQUIRED`.

## Feature Equations

The feature builder uses explicit aggregate values:

```text
token_consumption_change = sum(current_token_values) / sum(previous_token_values) - 1

capex_growth_t = capex_t / capex_t_minus_1 - 1
capex_growth_t_minus_1 = capex_t_minus_1 / capex_t_minus_2 - 1
capex_acceleration = capex_growth_t - capex_growth_t_minus_1
```

Direction rules:

- value > 0: expanding or accelerating
- value < 0: contracting or decelerating
- value == 0: stable

If normalization metadata is not approved, raw directional features may still be
computed, but normalized directional scores are not computed and
`REVIEW_REQUIRED` is attached.

## Scenario Grid

Scenario IDs are explanation-only labels over two directions:

| Scenario | Token consumption | Capex acceleration |
|---|---|---|
| S1 | expanding | accelerating |
| S2 | expanding | stable |
| S3 | expanding | decelerating |
| S4 | stable | accelerating |
| S5 | stable | stable |
| S6 | stable | decelerating |
| S7 | contracting | accelerating |
| S8 | contracting | stable |
| S9 | contracting | decelerating |

The scenario engine builds a continuous probability distribution. It does not
map a scenario to a fixed allocation, target weight, order, or sell action.

## Distribution Rule

The current diagnostic implementation uses `membership_strength` from test or
approved config input. Token-direction membership and capex-direction membership
are multiplied for each scenario and normalized so S1-S9 sum to `1.0`.

If scenario parameters are missing or invalid, the engine returns a neutral
distribution with `REVIEW_REQUIRED`.

## Sector Components

Implemented diagnostic sector component outputs:

- `bigtech_platform`
- `power_equipment`
- `semiconductor_hbm`
- `cash_short_duration`
- `inverse_hedge_diagnostic`

Each component returns:

- `sector_id`
- `as_of_date`
- `component_score`
- `confidence`
- `data_quality`
- `diagnostic_only`
- `scenario_distribution`
- `fallback_state`
- `reason_codes`
- `warnings`
- `parameter_version`
- `model_version`

`inverse_hedge_diagnostic` is evidence only and includes
`requires_existing_hedge_policy`. It does not create inverse orders or target
weights.

## Macro Overlay

Macro overlay consumes these stress keys when present:

- `real_rate_shock_score`
- `credit_spread_stress_score`
- `liquidity_stress_score`
- `fx_stress_score`
- `volatility_stress_score`

The overlay reduces component confidence and records macro metadata. It leaves
scenario probabilities unchanged and does not increase risk.

## Parameter Metadata

`config/scoring/ai_capex_token.yaml` is intentionally draft metadata:

- `enabled: false`
- `production_enabled: false`
- `diagnostic_only: true`
- `approved: false`
- production gate requires approved parameters, passing backtest,
  walk-forward validation, and user approval.

Unapproved values are not production defaults. Test-only parameters are scoped
under `test_parameters`.

## Fallbacks

Allowed fallback states are:

- `NO_ACTION`
- `HOLD`
- `REVIEW_REQUIRED`
- `RISK_REDUCE_ONLY`
- `diagnostic_only`

Risk-increasing fallbacks are invalid.

## No-Order Boundary

The AI Capex-Token component must not emit:

- broker payloads;
- order candidates;
- order submission requests;
- live execution flags;
- fixed target weights;
- automatic inverse hedge actions.

Outputs are diagnostic score/component contracts only.

## Testing Requirement

Required coverage exists for:

- pure domain contracts;
- config metadata loading;
- explicit fixture schema;
- input adapter and point-in-time filtering;
- feature builder;
- scenario engine;
- sector components;
- macro overlay;
- diagnostic integration with sector scoring boundary;
- input-to-score E2E flow;
- backtest-time future data leakage prevention;
- architecture boundaries.
