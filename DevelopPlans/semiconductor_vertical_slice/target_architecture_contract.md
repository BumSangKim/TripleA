# SEM-001 Semiconductor Vertical-Slice Target Contract

## Intent

The semiconductor slice is a fixture-based, deterministic, point-in-time,
review-only extension. It preserves the current architecture composition and
uses existing data, domain, score-pipeline, strategy, constraint, backtest,
and audit boundaries where they already fit.

## Portfolio posture

- Strategic core benchmark: **MSCI World**.
- Semiconductor role: active overlay / active tilt relative to that core.
- Initial contribution: non-activating and review-only.
- Production activation: disabled until an explicit owner approval and the
  later backtest gates pass.
- Permitted conservative outputs on missing, stale, ambiguous, or invalid
  input: `NO_ACTION`, `HOLD`, `REVIEW_REQUIRED`, `RISK_REDUCE_ONLY`.

## Target data-to-output flow

```text
Semiconductor raw fixture or read-only source
-> existing point-in-time raw/snapshot contracts
-> normalized and smoothed feature values
-> global demand, memory, inventory/supply, equipment/capacity,
   earnings-quality, and market feature groups
-> subsector and sector/asset diagnostic scores
-> macro fit and risk penalty
-> MSCI World look-through overlap control
-> risk-budgeted active tilt proposal
-> existing hard constraints and simulation-only rebalancing output
-> decision snapshot, backtest, audit, and shadow report
```

## Required boundaries

| Boundary | Contract direction | Current reuse point | Activation rule |
|---|---|---|---|
| Raw data | source/fixture -> `api/data` | `RawTimeSeriesPoint`, `RawCompanyMetricPoint`, `CapexRawSnapshotBuilder` | `available_at` and source metadata are mandatory. |
| Features | snapshot -> independent feature contracts | `HistoricalSnapshot`, `CapexFeatureMaterializer`, AI CAPEX input contracts | New feature calculators must not import allocation, rebalancing, or execution code. |
| Scores | features -> diagnostic score contracts | `CommonSectorScoringEngine`, `AICapexTokenSectorComponentBuilder` | Subsector/sector scores are continuous, traceable, and non-activating. |
| Macro/risk | scores -> conservative penalties | macro distribution and `RiskBudgetEngine` | Existing macro/risk behavior is characterized, not altered, until a dedicated task approves change. |
| Look-through | benchmark/ETF holdings -> overlap exposure | existing portfolio look-through config concepts | MSCI World identifier and point-in-time holdings must exist before computation. |
| Allocation/rebalancing | proposal -> hard constraints -> simulation output | allocation offsets, rebalancing service, account constraints | No semiconductor proposal enters the active allocation path in this task pack before an explicit activation gate. |
| Backtest/audit | point-in-time inputs -> deterministic report | `PipelineBacktestRunner`, backtests service/ports, audit contracts | Future data must be rejected and reports must carry reason codes and versions. |

## Parameter contract

All candidate ranges, weights, smoothing methods, penalties, look-through caps,
and risk limits belong in versioned configuration. A parameter is inactive when
its approval/backtest gate is absent or false, consistent with
`api.score_pipeline.parameters.ParameterRegistry`.

## Non-goals for this slice

- No live broker submission, notification delivery, real-account mutation, or
  automatic execution.
- No direct S1-S9 or semiconductor-feature mapping to buy/sell, fixed weights,
  or executable orders.
- No replacement of MSCI World core with semiconductor exposure.
- No change to current macro thresholds, active sector tilt, risk budget,
  allocation, rebalancing, or order-candidate behavior without an explicitly
  scoped downstream task.
