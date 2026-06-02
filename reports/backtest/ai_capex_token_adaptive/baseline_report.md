# AI Capex-Token Adaptive Baseline Report

Report version: `ai_capex_token_adaptive_baseline_v1`

## Mode

- Production enabled: `False`
- Diagnostic only: `True`
- Shadow candidate only: `True`

## Memory Cycle Coverage

- Status: `PASS_TWO_OR_MORE_CYCLES`
- Complete cycles: `2`
- Proxies: `dram_asp_index`

## Baselines

### score_pipeline_without_ai_capex_token

- Allocation contribution: `0.0`
- Final allocation changed: `False`
- Cost-adjusted return: `0.0`
- Turnover: `0.0`

### legacy_ai_capex_cycle_diagnostic

- Allocation contribution: `0.0`
- Final allocation changed: `False`
- Cost-adjusted return: `0.0`
- Turnover: `0.0`

### adaptive_ai_capex_token_zero_contribution

- Allocation contribution: `0.0`
- Final allocation changed: `False`
- Cost-adjusted return: `0.0`
- Turnover: `0.0`

### conservative_fallback_poor_missing_data

- Allocation contribution: `0.0`
- Final allocation changed: `False`
- Cost-adjusted return: `0.0`
- Turnover: `0.0`

## Warnings

- tax modeling is unavailable in the current score_pipeline backtest engine; tax-adjusted validity is not claimed
- drawdown duration and worst-window metrics are unsupported by the current baseline fixture and remain null
- adaptive AI Capex-Token contribution is zero and diagnostic-only
