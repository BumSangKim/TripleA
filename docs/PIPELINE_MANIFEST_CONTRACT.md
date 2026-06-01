# Pipeline Manifest Contract

The investment decision pipeline is declared in
`config/pipelines/investment_decision.yaml` and loaded by
`api.score_pipeline.pipeline_manifest`.

The manifest is a contract and validation aid. It does not execute trades,
submit broker orders, or promote parameters automatically.

## Required Manifest Fields

- `version`: integer manifest version.
- `name`: non-empty manifest name.
- `execution_mode_default`: default review mode. The current manifest uses
  `review_required`.
- `auto_execution_allowed`: must be `false`.
- `fallback_policy.allowed_actions`: conservative actions only.
- `fallback_policy.forbidden_actions`: aggressive or execution actions that
  must not be used as fallbacks.
- `stages`: ordered list of pipeline stages.

## Conservative Fallback Policy

Allowed fallback actions are limited to:

- `NO_ACTION`
- `HOLD`
- `REVIEW_REQUIRED`
- `RISK_REDUCE_ONLY`

Forbidden fallback actions include:

- `BUY`
- `INCREASE_RISK`
- `INCREASE_SATELLITE_WEIGHT`
- `FORCE_REBALANCE`
- `AUTO_EXECUTE`

If uncertainty cannot be resolved from available data, the pipeline must choose
a conservative fallback or require review. Missing business rules must not be
invented in source code.

## Required Stage Order

The validator requires these stage IDs to exist in order-compatible form:

| Stage | Layer | Required input meaning | Required output meaning | Validation meaning |
|---|---|---|---|---|
| `collect_raw_data` | data | Source availability. | Raw data snapshot and quality metadata. | Source presence, dates, no future data, stale checks. |
| `build_features` | feature | Raw data plus quality metadata. | Feature snapshot. | Feature version and missing-ratio checks. |
| `calculate_scores` | score | Feature snapshot. | Score snapshot. | Score contract, confidence, and data-quality fields. |
| `macro_regime_distribution` | macro regime engine | Score snapshot. | Regime distribution. | Distribution sums to one; dominant regime is descriptive only. |
| `sector_asset_scoring` | sector scoring engine | Scores plus regime distribution. | Sector and asset scores. | Component and confidence fields are present. |
| `risk_budget` | risk budget engine | Scores plus account state. | Risk budget result. | Portfolio/account risk checks. |
| `allocation` | allocation engine | Risk result plus scores and positions. | Target weight ranges. | Range and gradual-change checks. |
| `rebalancing` | rebalancing engine | Target ranges plus positions. | Rebalance intensity and candidates. | Intensity and turnover checks. |
| `hard_constraint_filter` | account constraint engine | Rebalance candidates plus constraints. | Validated candidates. | Hard constraints block before downstream use. |
| `order_candidate_generation` | execution engine | Validated candidates. | Manual-review order candidates. | Review required; no live execution by default. |
| `audit_report` | reporting/audit | Candidates plus intermediate outputs. | Decision log and warnings. | Reason codes, versions, and dates are present. |

The manifest validator also enforces:

- `collect_raw_data` is the first stage.
- `audit_report` is the last stage.
- `hard_constraint_filter` runs before `order_candidate_generation`.
- stage IDs are unique.
- allowed and forbidden fallback actions do not overlap.
- aggressive fallback actions are not allowed.

## Validation Commands

```bash
.venv/bin/python -m pytest tests/unit/score_pipeline/test_pipeline_manifest.py -q
.venv/bin/python -m pytest tests/architecture/test_pipeline_manifest_file.py -q
.venv/bin/python -m pytest tests/architecture/test_pipeline_manifest_contract.py -q
```

The broader modular-monolith validation suite is:

```bash
.venv/bin/python -m pytest tests/architecture -q
.venv/bin/python -m pytest tests/integration/pipeline -q
.venv/bin/python -m pytest tests/unit/score_pipeline -q
```

