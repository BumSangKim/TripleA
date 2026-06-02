# AI Capex-Token Normalization and Scenario Smoothing Tuning

Report version: `ai_capex_token_normalization_smoothing_tuning_v1`

## Selected Diagnostic Candidate

- Candidate: `hybrid_percentile_zscore_lb48_min18_win0.0_exponential_0.25`
- Method: `hybrid_percentile_zscore`
- Lookback months: `48`
- Min observations: `18`
- Winsorization: `0.0`
- Smoothing: `exponential`
- Scenario turnover: `0.0726`
- Detection delay periods: `1.15`
- CAGR rank: `49`

## Selection Criteria

- leakage_safety
- memory_cycle_coverage
- lower_scenario_turnover_whipsaw
- acceptable_detection_delay
- stable_calibration_across_memory_cycle_phases
- no_excessive_lookback_sensitivity
- explainability
- cagr_analysis_only_after_gates

## Sensitivity

- `hybrid_percentile_zscore` median turnover `0.1142`
- `robust_zscore` median turnover `0.13`
- `rolling_percentile` median turnover `0.1682`

## Warnings

- selected candidate is diagnostic-only and not approved for production
- CAGR is analysis-only and is evaluated after leakage, memory-cycle, turnover, delay, stability, sensitivity, and explainability gates
- no sector weight, order candidate, or allocation target is tuned in this task
