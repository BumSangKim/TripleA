# AI Capex-Token Audit Reason Codes

This document lists reason codes and warning strings currently emitted by the
AI Capex-Token implementation. It intentionally avoids defining future reason
codes that are not present in code.

## Input Validation

| Code | Emitted by | Meaning |
|---|---|---|
| `UNSUPPORTED_INPUT_PAYLOAD` | input adapter error | Payload is not a mapping, plugin-style `.data` object, or object with fields. |
| `INVALID_EXPLICIT_PERIOD_ROLE_REVIEW_REQUIRED` | input adapter | A metric row is malformed or uses an unsupported/missing explicit `period_role`. |
| `MISSING_TOKEN_CURRENT_REVIEW_REQUIRED` | input adapter | No eligible current token metric remains after validation and PIT filtering. |
| `MISSING_TOKEN_PREVIOUS_REVIEW_REQUIRED` | input adapter | No eligible previous token metric remains after validation and PIT filtering. |
| `MISSING_CAPEX_PERIOD_REVIEW_REQUIRED` | input adapter or feature builder | Required `t`, `t_minus_1`, or `t_minus_2` capex role is missing. |
| `TOKEN_PREVIOUS_INVALID_REVIEW_REQUIRED` | feature builder | Previous token aggregate is zero or negative, so token change is unsafe. |
| `CAPEX_PREVIOUS_INVALID_REVIEW_REQUIRED` | feature builder | Prior capex denominator is zero or negative, so capex growth is unsafe. |
| `NEGATIVE_TOTAL_REVIEW_REQUIRED` | feature builder | A required aggregate is negative and cannot be interpreted conservatively. |

## Future Data Exclusion

| Code | Emitted by | Meaning |
|---|---|---|
| `FUTURE_INPUT_EXCLUDED` | input adapter | At least one metric had `available_at` after the decision time and was excluded. |

Future rows are not passed into feature construction. If exclusion leaves a
required role missing, the adapter returns or raises `REVIEW_REQUIRED`.

## Missing Parameters

| Code or warning | Emitted by | Meaning |
|---|---|---|
| `NORMALIZATION_PARAMETERS_REVIEW_REQUIRED` | feature builder | Normalization metadata is not approved, so normalized directional scores are not computed. |
| `normalized_directional_scores_not_computed` | feature builder warning | Diagnostic feature values exist, but normalized score parameters are not production-approved. |
| `SCENARIO_PARAMETERS_REVIEW_REQUIRED` | scenario engine | Scenario probability parameters are missing, invalid, or feature fallback is active. |
| `scenario_distribution_diagnostic_only` | scenario engine warning | Scenario distribution is neutral/diagnostic because parameters or input quality are insufficient. |

## Poor Data Quality

| Code | Emitted by | Meaning |
|---|---|---|
| `LOW_DATA_QUALITY_REVIEW_REQUIRED` | input adapter or feature builder | At least one metric has low quality, high missing ratio, or stale status. |

Poor data quality may reduce confidence. It must not increase risk.

## Scenario Distribution

| Code | Emitted by | Meaning |
|---|---|---|
| `AI_CAPEX_TOKEN_SCENARIO_DISTRIBUTION` | scenario engine | A valid S1-S9 continuous probability distribution was produced. |

The dominant scenario is explanation-only. It is not an investment switch.

## Sector Evidence

| Code pattern | Emitted by | Meaning |
|---|---|---|
| `ai_capex_token_sector_component` | sector component builder | Diagnostic sector component score was produced. |
| `missing_<metric_key>_review_required` | sector component builder | Optional sector evidence metric is missing; confidence is lowered and fallback may be `REVIEW_REQUIRED`. |
| `cash_defensive_diagnostic` | sector component builder | Cash/short-duration diagnostic component uses defensive scenario probability, data quality, and macro stress. |
| `inverse_hedge_diagnostic_only` | sector component builder | Inverse hedge evidence is diagnostic only. |
| `requires_existing_hedge_policy` | sector component builder | Inverse hedge evidence requires a separate approved hedge policy before any use. |
| `feature_fallback_review_required` | diagnostic component | Feature fallback propagated to sector components. |

Known sector metric names used by missing-metric reason codes:

- `ai_monetization_score`
- `fcf_margin_improvement_score`
- `capex_burden_score`
- `valuation_burden_score`
- `backlog_slowdown_score`
- `asp_slowdown_score`
- `backlog_growth_score`
- `asp_growth_score`
- `hbm_supply_growth_score`
- `hbm_inventory_risk_score`
- `hbm_asp_growth_score`

## Macro Overlay

| Code | Emitted by | Meaning |
|---|---|---|
| `AI_CAPEX_TOKEN_MACRO_OVERLAY` | macro overlay | Macro overlay was applied. |
| `macro_overlay_confidence_adjustment` | macro overlay | Component confidence was reduced according to macro stress. |
| `MISSING_MACRO_OVERLAY_REVIEW_REQUIRED` | macro overlay result | Required macro stress keys are missing. |
| `missing_macro_overlay_review_required` | macro overlay component reason | Component confidence was reduced because macro overlay inputs are missing. |

The macro overlay adjusts confidence and metadata only. Scenario probabilities
remain unchanged.

## Diagnostic And Production Gate

| Code | Emitted by | Meaning |
|---|---|---|
| `AI_CAPEX_TOKEN_DIAGNOSTIC_ONLY` | diagnostic component | Output is separate diagnostic evidence and was not applied to the sector engine. |

Current gate state:

- config `enabled` defaults to `false`;
- config `production_enabled` defaults to `false`;
- config `diagnostic_only` defaults to `true`;
- parameter metadata is `approved: false`;
- production use requires explicit approval, backtest pass, and walk-forward pass.

## Forbidden Audit Outcomes

These values are rejected as fallback states or forbidden as emitted actions:

- `BUY`
- `INCREASE_RISK`
- `INCREASE_SATELLITE_WEIGHT`
- `FORCE_REBALANCE`
- `AUTO_EXECUTE`
- `LIVE_EXECUTE`

If any future implementation needs investment action, it belongs outside this
diagnostic component and requires separate owner approval, backtesting, and
hard-constraint review.
