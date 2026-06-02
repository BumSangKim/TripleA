# AI Capex-Token Penalty, Macro Overlay, and Turnover Control Tuning

Report version: `ai_capex_token_penalty_overlay_turnover_tuning_v1`

## Selected Diagnostic Controls

- Candidate: `penalty_overlay_turnover_controls_midgrid_v1`
- Allocation contribution: `0.0`
- Ready for allocation contribution: `False`

## Scenario Results

- `base` contribution `0.05`, intensity `0.02425`
- `poor_data` contribution `0.043838`, intensity `0.018273`
- `stale_data` contribution `0.036847`, intensity `0.011491`
- `macro_stress` contribution `0.035683`, intensity `0.010363`
- `high_valuation` contribution `0.046527`, intensity `0.020881`
- `high_turnover` contribution `0.049838`, intensity `0.020367`
- `no_turnover_penalty_reference` contribution `0.05`, intensity `0.025`

## Rejected Candidates

- `zero_penalty_return_chasing`: `PENALTY_BYPASS_DETECTED`
- `mdd_worsening_candidate`: `MDD_WORSENED`
- `turnover_spike_candidate`: `TURNOVER_SPIKE_DETECTED`
- `poor_data_risk_increase_candidate`: `POOR_DATA_RISK_INCREASE_DETECTED`
- `macro_stress_risk_amplifier`: `MACRO_STRESS_RISK_AMPLIFICATION_DETECTED`
- `high_valuation_momentum_chasing`: `HIGH_VALUATION_MOMENTUM_CHASING_DETECTED`
- `inverse_performance_dominance`: `INVERSE_PERFORMANCE_DOMINANCE_DETECTED`
