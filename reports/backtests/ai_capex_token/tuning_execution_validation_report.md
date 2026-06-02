# AI Capex-Token Tuning Execution Validation Report

- status: `PASS_SYNTHETIC_ONLY`
- diagnostic_only: `True`
- production_ready: `False`
- candidate_count: `4`
- selected_candidate_id: `candidate_sensitive`
- no_op_tuning_detected: `False`
- leakage_check_passed: `True`

## Memory Cycle Coverage

- status: `PASS_TWO_MEMORY_CYCLES`
- distinct_cycle_count: `2`
- cycle_ids: `cycle_a, cycle_b`
- historical_tuning_allowed: `True`

## Candidate Summary

| candidate_id | objective_score | output_signature | metric_signature | rejected |
|---|---:|---|---|---|
| baseline | 3.281077 | `b03f04389558` | `2490e6c8df40` | `False` |
| candidate_low_smoothing | 3.007115 | `3b7500bd205c` | `3abb1bf2ce8b` | `True` |
| candidate_balanced | 3.238289 | `033d2cc1e4e9` | `90efe4891749` | `True` |
| candidate_sensitive | 3.505504 | `e912efb2906c` | `02704b1cadb9` | `False` |

## Rejected Candidates

- `candidate_low_smoothing`: OBJECTIVE_BELOW_BASELINE_DIAGNOSTIC_REJECTED
- `candidate_balanced`: OBJECTIVE_BELOW_BASELINE_DIAGNOSTIC_REJECTED

## Objective Breakdown

### baseline

- risk_adjusted_return: `0.1567823796875`
- turnover_efficiency: `0.8`
- cycle_stability: `0.8242947114577897`
- parameter_robustness: `1.0`
- explainability: `0.7`
- penalties: `{"cagr_only_penalty": 0.0, "mdd_worsening_penalty": 0.0, "missing_output_penalty": 0.0, "one_cycle_only_penalty": 0.0, "turnover_penalty": 0.2}`

### candidate_low_smoothing

- risk_adjusted_return: `0.0735439974609375`
- turnover_efficiency: `0.7`
- cycle_stability: `0.8335711307375755`
- parameter_robustness: `1.0`
- explainability: `0.7`
- penalties: `{"cagr_only_penalty": 0.0, "mdd_worsening_penalty": 0.0, "missing_output_penalty": 0.0, "one_cycle_only_penalty": 0.0, "turnover_penalty": 0.3}`

### candidate_balanced

- risk_adjusted_return: `0.10557869410156252`
- turnover_efficiency: `0.8`
- cycle_stability: `0.8327105869622725`
- parameter_robustness: `1.0`
- explainability: `0.7`
- penalties: `{"cagr_only_penalty": 0.0, "mdd_worsening_penalty": 0.0, "missing_output_penalty": 0.0, "one_cycle_only_penalty": 0.0, "turnover_penalty": 0.2}`

### candidate_sensitive

- risk_adjusted_return: `0.19318148062499998`
- turnover_efficiency: `0.9`
- cycle_stability: `0.8123221580171113`
- parameter_robustness: `1.0`
- explainability: `0.7`
- penalties: `{"cagr_only_penalty": 0.0, "mdd_worsening_penalty": 0.0, "missing_output_penalty": 0.0, "one_cycle_only_penalty": 0.0, "turnover_penalty": 0.1}`

## Leakage / No-Op Checks

- unique_parameter_hash_count: `4`
- unique_output_signature_count: `4`
- unique_metric_signature_count: `4`
- leakage warning `FUTURE_INPUT_EXCLUDED`: future.leakage_probe
- leakage warning `FUTURE_INPUT_EXCLUDED`: future.leakage_probe
- leakage warning `FUTURE_INPUT_EXCLUDED`: future.leakage_probe
- leakage warning `FUTURE_INPUT_EXCLUDED`: future.leakage_probe
