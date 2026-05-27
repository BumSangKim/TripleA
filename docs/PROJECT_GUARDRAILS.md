# Project Guardrails

## 1. Purpose

This document defines non-negotiable engineering and investment-safety rules for the project.

It summarizes the operational rules that must be followed before changing strategy, backtest, allocation, order-candidate, broker/API, or execution-related behavior. The detailed source of truth remains `docs/MASTER_DEVELOPMENT_GUIDE.md`.

## 2. Core Rules

```text
No Threshold Switch.
Use Score Flow.
Hard Constraints First.
Backtest Before Execution.
Explain Every Decision.
Use conservative fallback on uncertainty or errors.
Do not hardcode strategy parameters.
Do not default to automatic execution.
```

## 3. Execution Policy

Automatic execution is prohibited by default.

Allowed before real account integration:

- historical backtest simulation;
- paper calculation;
- order candidate generation;
- validation-only order checks;
- user review output;
- decision logs.

Not allowed before explicit later approval:

- real order submission;
- account-linked automatic execution;
- automatic order retry;
- live position-changing workflow;
- silent execution after signal generation.

Existing `/api/orders/execute` behavior must remain log-only unless a later approved task explicitly changes the execution policy. Live mode must stay read-only until a separate safety-reviewed execution phase.

## 4. Strategy Decision Policy

All investment decisions must flow through:

```text
Raw Data
-> Feature Layer
-> Score Layer
-> Macro Regime Score Distribution
-> Sector / Asset Score
-> Risk Budget Score
-> Allocation Score
-> Rebalancing Intensity Score
-> Hard Constraint Filter
-> Order Candidate
-> User Review
```

Prohibited shortcuts:

- Raw Data -> Buy/Sell;
- Single Indicator -> Regime Switch;
- Dominant Regime Label -> Fixed Weights;
- Sector Name -> Hardcoded Weight;
- Backtest Return -> Production Strategy.

## 5. Threshold Policy

Thresholds are allowed for:

- missing data detection;
- stale data detection;
- anomalous data detection;
- account/legal constraints;
- order safety checks;
- minimum order size checks;
- score normalization boundaries;
- warning levels;
- emergency circuit breakers.

Thresholds must not directly trigger:

- macro regime switching;
- risk-on/risk-off switching;
- sudden equity/bond/cash allocation changes;
- direct buy/sell decisions;
- direct sector inclusion or exclusion;
- immediate target weight expansion.

If an existing threshold is found in strategy logic, treat it as a gap to be documented or refactored in a later approved task, not as a pattern to copy.

## 6. Hard Constraint Policy

Hard constraints override scores.

Examples:

- account type restrictions;
- tradability restrictions;
- risky-asset limits;
- insufficient cash;
- minimum order unit;
- missing balance;
- API state unknown;
- trading halt;
- order validation failure.

If hard constraint data is missing or stale, the safe default is `REVIEW_REQUIRED` or `NO_ACTION`, not a best-effort buy/sell decision.

## 7. Data Quality Policy

Poor data quality must not increase risk.

Allowed responses:

- reduce signal weight;
- hold;
- review required;
- conservative fallback;
- risk reduce only.

Data used for backtests and simulated decisions must be available as of the simulated decision date. Future price data, revised macro data treated as originally available, and future constituent data are prohibited.

## 8. Parameter Policy

Strategy parameters must be configurable and versioned.

Do not hardcode:

- score weights;
- lookback windows;
- target weights;
- rebalancing bands;
- sector caps;
- account risk limits;
- transaction cost assumptions;
- tax assumptions.

When a parameter is missing, invalid, or unapproved, use `HOLD`, `REVIEW_REQUIRED`, or `RISK_REDUCE_ONLY`. Do not silently substitute a risk-increasing default.

## 9. Backtest Policy

No strategy logic may be promoted without backtesting.

Backtests must avoid:

- future-data leakage;
- survivorship bias;
- revised macro data treated as historically available;
- future price or constituent data in current decisions.

Backtest outputs must include enough explanation to connect decisions back to scores, constraints, parameters, costs, and data quality.

## 10. Failure and Uncertainty Policy

When uncertain, default to:

```text
NO_ACTION
HOLD
REVIEW_REQUIRED
RISK_REDUCE_ONLY
```

Never default to:

```text
BUY
INCREASE_RISK
INCREASE_SATELLITE_WEIGHT
FORCE_REBALANCE
```

Errors from data providers, broker APIs, account sync, missing configuration, or unexpected response shapes must not trigger risk-increasing decisions.

## 11. Coding Agent Rules

Before editing code, Codex must:

1. inspect current structure;
2. identify the minimal safe change;
3. preserve existing behavior unless explicitly required;
4. avoid broad refactoring;
5. add or update tests when strategy logic changes;
6. document non-trivial decisions;
7. avoid inventing missing business rules.

For documentation-only Phase 0 tasks, Codex must not alter production logic to make the documentation easier to write.

