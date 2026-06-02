# AI Capex-Token Sector Component and Dampening Tuning

Report version: `ai_capex_token_sector_component_tuning_v1`

## Selected Diagnostic Candidate

- Candidate: `sector_components_midgrid_penalty_preserving_v1`
- Normalization candidate: `hybrid_percentile_zscore_lb48_min18_win0.0_exponential_0.25`
- Aggregate component score: `0.070938`
- Inverse share: `0.137247`

## Sector Explanations

- `bigtech_platform`: BigTech platform combines AI monetization, capex burden relief, FCF improvement, and valuation penalty as a score component.
- `power_equipment`: Power equipment combines capex acceleration context, backlog, ASP, valuation burden, and market-state dampeners.
- `semiconductor_hbm`: Semiconductor HBM combines token demand context, HBM ASP, supply shortage, inventory risk, valuation burden, and dampeners.
- `cash_short_duration`: Reports defensive cash/short-duration context from data quality, macro stress, memory-cycle phase, and turnover pressure.
- `inverse_hedge_diagnostic`: Reports inverse hedge context only for user review; it cannot dominate or generate orders.

## Rejected Controls

- `valuation_penalty_zero_bypass`: `PENALTY_BYPASS_DETECTED`
- `data_quality_penalty_zero_bypass`: `PENALTY_BYPASS_DETECTED`
- `macro_stress_redefines_scenario`: `MACRO_STRESS_CANNOT_REDEFINE_SCENARIO`
- `turnover_penalty_zero_bypass`: `PENALTY_BYPASS_DETECTED`
- `inverse_dominance_control`: `INVERSE_DOMINANCE_DETECTED`
