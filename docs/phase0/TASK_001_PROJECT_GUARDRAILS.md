# TASK_001 — Project Guardrails

## Objective

Create a concise project guardrails document that Codex and future contributors must follow before making strategy, backtest, allocation, order-candidate, or execution-related changes.

The document must enforce the project's core principles:

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

## Scope

Allowed changes:

- create or update `docs/PROJECT_GUARDRAILS.md`;
- reference the master guide at a high level;
- define prohibited implementation patterns;
- define conservative fallback behavior;
- define execution boundaries before real account integration.

Not allowed:

- modifying strategy code;
- adding order submission logic;
- enabling broker execution;
- adding automatic execution;
- changing existing parameters;
- implementing account constraints in code;
- implementing allocation or backtest logic.

## Required References

Read before starting:

- `AGENTS.md`, if present;
- `MASTER_DEVELOPMENT_GUIDE.md`, if present;
- `DevelopPlans/STATUS.md`;
- `docs/PHASE_0_REPOSITORY_AUDIT.md`, if present.

## Required Output File

Create or update:

```text
docs/PROJECT_GUARDRAILS.md
```

## Required Document Structure

Use this structure:

```markdown
# Project Guardrails

## 1. Purpose

This document defines non-negotiable engineering and investment-safety rules for the project.

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

## 4. Strategy Decision Policy

All investment decisions must flow through:

Raw Data
→ Feature Layer
→ Score Layer
→ Macro Regime Score Distribution
→ Sector / Asset Score
→ Risk Budget Score
→ Allocation Score
→ Rebalancing Intensity Score
→ Hard Constraint Filter
→ Order Candidate
→ User Review

Prohibited shortcuts:

- Raw Data → Buy/Sell;
- Single Indicator → Regime Switch;
- Dominant Regime Label → Fixed Weights;
- Sector Name → Hardcoded Weight;
- Backtest Return → Production Strategy.

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

## 7. Data Quality Policy

Poor data quality must not increase risk.

Allowed responses:

- reduce signal weight;
- hold;
- review required;
- conservative fallback;
- risk reduce only.

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

## 9. Backtest Policy

No strategy logic may be promoted without backtesting.

Backtests must avoid:

- future-data leakage;
- survivorship bias;
- revised macro data treated as historically available;
- future price or constituent data in current decisions.

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

## 11. Coding Agent Rules

Before editing code, Codex must:

1. inspect current structure;
2. identify the minimal safe change;
3. preserve existing behavior unless explicitly required;
4. avoid broad refactoring;
5. add or update tests when strategy logic changes;
6. document non-trivial decisions;
7. avoid inventing missing business rules.
```

## Implementation Steps

1. Read required references.
2. Create or update `docs/PROJECT_GUARDRAILS.md`.
3. Keep the document concise and operational.
4. Do not modify code.
5. Update `DevelopPlans/STATUS.md`.

## Test Command

This task does not require functional tests.

If markdown linting exists, run it.

Otherwise document:

```text
No test command was run because this task only creates project guardrail documentation.
```

## Acceptance Criteria

This task is complete only if:

- [ ] `docs/PROJECT_GUARDRAILS.md` exists;
- [ ] the document includes execution policy;
- [ ] the document includes strategy decision policy;
- [ ] the document includes threshold policy;
- [ ] the document includes hard constraint policy;
- [ ] the document includes data quality policy;
- [ ] the document includes parameter policy;
- [ ] the document includes backtest policy;
- [ ] no production logic is changed;
- [ ] `DevelopPlans/STATUS.md` is updated;
- [ ] Codex stops after this task.


---

## Mandatory Task Loop

Codex must follow this loop:

1. Read required references.
2. Inspect the relevant repository structure and files.
3. Make the minimal safe change required by this task.
4. Run the required test command.
5. If the test fails because of this task, fix the issue and rerun the test.
6. Repeat until acceptance criteria pass or a blocker is clearly documented.
7. Update `DevelopPlans/STATUS.md`.
8. Stop after this task. Do not start the next task.

## Universal Prohibitions

Do not:

- add live execution;
- add real account order submission;
- add broker-linked trading behavior;
- introduce automatic execution;
- hardcode investment strategy parameters;
- convert raw indicators directly into buy/sell decisions;
- perform broad refactoring;
- invent missing investment rules;
- proceed to the next task without explicit user instruction.

## Conservative Fallback

If uncertainty blocks implementation, use or document one of:

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

## Completion Report Required

At the end, report:

- files created or modified;
- tests run;
- test result;
- assumptions made;
- blockers or open questions;
- whether this task is complete;
- next recommended task.
