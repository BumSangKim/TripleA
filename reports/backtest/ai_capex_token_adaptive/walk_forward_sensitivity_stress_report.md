# AI Capex-Token Walk-Forward, Sensitivity, and Stress Validation

Report version: `ai_capex_token_walk_forward_sensitivity_stress_v1`
Validation status: `PASS_DIAGNOSTIC_ONLY`

## Top Candidates

- `normalization_smoothing`: `hybrid_percentile_zscore_lb48_min18_win0.0_exponential_0.25`
- `sector_components`: `sector_components_midgrid_penalty_preserving_v1`
- `penalty_overlay_turnover`: `penalty_overlay_turnover_controls_midgrid_v1`

## Memory-Cycle Phase Metrics

- `recovery`: cost-adjusted `0.0`, max drawdown `-0.012`
- `normalization`: cost-adjusted `0.0`, max drawdown `-0.018`
- `stress`: cost-adjusted `0.0`, max drawdown `-0.032`

## Warnings

- rolling training windows are used where individual splits have limited history
- validation remains diagnostic-only and does not create production parameters
- tax-adjusted metrics are unsupported and remain explicitly null
