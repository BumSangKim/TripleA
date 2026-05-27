# Pre-Execution Score Flow Phases 6-13

This document summarizes the non-executing foundations added for Phases 6 through 13.

## Phase 6 Backtest Foundation

`api/backtest_foundation.py` defines leakage-safe simulation contracts, a deterministic simulation clock, historical snapshot loader interface, simulated portfolio state transitions, cost/tax hooks, metric calculation, and a plug-in runner. It does not call broker APIs or submit orders.

## Phase 7 Macro Regime Distribution

`MacroRegimeDistributionEngine` produces a normalized regime distribution with dominant regime marked as explanation-only. It does not map regime labels to fixed target weights.

## Phase 8 Sector Scoring

`SectorScoringEngine` loads sector definitions from config and produces decomposable sector scores with component reasons, warnings, confidence, data quality, and deterministic ranking. It does not generate orders.

## Phase 9 Risk Budget

`RiskBudgetScoringEngine` separates portfolio risk budget, account risk budget, soft penalties, and hard blocking conditions. Missing account state or hard limit violations block risk-increasing interpretation.

## Phase 10 Allocation

`ScoreBasedAllocationEngine` computes gradual, bounded target weights from macro distribution, sector score, risk budget, and hard constraint state. Residual capital is handled through the configured cash bucket.

## Phase 11 Rebalancing

`RebalancingIntensityEngine` produces action semantics such as `NO_ACTION`, `BUY_CANDIDATE`, `HOLD_OVERWEIGHT_WINNER`, `PARTIAL_REDUCTION_CANDIDATE`, `RISK_REDUCE_ONLY`, and `REVIEW_REQUIRED`. It avoids mechanical selling of improving overweight winners unless risk pressure overrides.

## Phase 12 Reporting And Audit

`api/strategy/audit_layer.py` provides machine-readable decision logs, decision traces, warning aggregation, reason-code catalog validation, deterministic backtest report generation, and explanation service output derived from logs.

## Phase 13 Order Candidate Generation

`api/strategy/order_candidates.py` converts rebalance actions into non-executable user-review candidates, validates account/asset/cash/price/minimum-order constraints, masks account labels, separates actionable/blocked/review-required items, and explicitly marks output as not executed.

## Guardrails

- No live execution path was added.
- No broker order submission path was added.
- No automatic execution path was added.
- Hard constraints remain blockers.
- Missing data and uncertainty fall back to review-required or blocked risk-increase behavior.
- Historical simulation rejects future snapshots.

