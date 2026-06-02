# AI Capex-Token Tuning Execution Test Spec

## Purpose

This spec defines how to decide whether the AI Capex-Token backtest tuning loop
actually executes. It does not approve production parameters and does not claim
investment performance.

## Required Measurements

- `candidate_count`: number of evaluated parameter candidates. Must be at
  least `3`.
- `parameter_hash`: deterministic hash of the candidate parameter payload.
- `output_signature`: deterministic signature of diagnostic output fields that
  should change when parameters affect the pipeline.
- `metric_signature`: deterministic signature of objective metrics and ranking
  fields.
- `unique_parameter_hash_count`: distinct candidate parameter hashes.
- `unique_output_signature_count`: distinct output signatures.
- `unique_metric_signature_count`: distinct metric signatures.

## PASS / REVIEW / FAIL Statuses

- `PASS_SYNTHETIC_ONLY`: synthetic two-cycle fixture proves the tuning loop is
  non-no-op, but historical two-memory-cycle coverage is not proven.
- `PASS_HISTORICAL_DIAGNOSTIC`: historical two-memory-cycle coverage and
  output variation are proven. This is still diagnostic-only, not production.
- `REVIEW_REQUIRED`: tuning structure exists, but data/source/cycle evidence is
  insufficient for historical validation.
- `FAIL_NOOP_TUNING`: candidate parameters do not change output signatures,
  metric signatures, objective ranking, reason codes, or score contribution.
- `FAIL_STATIC_MARKET_MAPPING`: fixed values or direct market-state/action
  mappings are found.
- `FAIL_LEAKAGE_RISK`: future data can influence candidate output, metrics, or
  ranking.

## No-Op Failure Criteria

Fail with `FAIL_NOOP_TUNING` if any of the following is true:

- all candidates have the same `output_signature`;
- parameter hashes differ but all metric signatures are identical;
- candidate ranking always equals input order;
- every objective score is identical;
- candidate reason codes and score contribution are identical across all
  candidates;
- baseline and all candidates have identical scenario, sector, and diagnostic
  output payloads.

## Memory Cycle Gate

Historical diagnostic pass is impossible unless at least two explicit memory
cycles are proven by one of:

- `snapshots[*].metadata.memory_cycle_id`;
- a cycle annotation file such as `config/backtests/memory_cycles.yaml`;
- an existing memory-cycle classifier output.

If this evidence is absent, historical validation must return
`REVIEW_REQUIRED`. Synthetic fixtures may still produce `PASS_SYNTHETIC_ONLY`
for tuning-loop execution.

## Objective Rules

CAGR-only optimization is forbidden.

Objective breakdown must include multiple components, such as:

```text
mdd_improvement
+ risk_adjusted_return
+ cycle_stability
+ parameter_robustness
+ turnover_efficiency
+ explainability
- overfit_penalty
- leakage_penalty
- cost_tax_penalty
- static_mapping_penalty
- complexity_penalty
```

Ranking must be explainable from this breakdown and must not directly map
`S1` through `S9`, dominant scenario, or a single indicator to buy/sell,
target weight, order candidate, broker action, or execution behavior.

## Required Final Report Fields

- `status`
- `candidate_count`
- `unique_parameter_hash_count`
- `unique_output_signature_count`
- `unique_metric_signature_count`
- `memory_cycle_coverage`
- `selected_candidate_id`
- `rejected_candidates`
- `objective_breakdown`
- `no_op_tuning_detected`
- `leakage_check_passed`
- `diagnostic_only`
- `production_ready`

## Production Approval Guardrail

The verification result must keep:

```yaml
diagnostic_only: true
production_ready: false
production_enabled: false
approved: false
```

This package must not modify broker, execution, account mutation, order
generation, or production approval paths.
