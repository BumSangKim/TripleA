# TASK_003 — Backtest-First Development Sequence

## Objective

Create a development sequence document that converts the master guide's high-level phase order into a concrete backtest-first roadmap.

The roadmap must explicitly defer real account integration and live execution until after backtesting, algorithm validation, order-candidate generation, and user-approved execution boundaries are complete.

## Scope

Allowed changes:

- create or update `docs/DEVELOPMENT_SEQUENCE_BACKTEST_FIRST.md`;
- define phase-by-phase objectives;
- define entry and exit criteria per phase;
- define what must not be implemented in early phases;
- align future task planning with the master guide.

Not allowed:

- implementing future phases;
- modifying strategy code;
- modifying tests except documentation checks;
- enabling broker execution;
- adding account-linked execution logic;
- changing allocation behavior.

## Required References

Read before starting:

- `AGENTS.md`, if present;
- `MASTER_DEVELOPMENT_GUIDE.md`, if present;
- `DevelopPlans/STATUS.md`;
- `docs/PHASE_0_REPOSITORY_AUDIT.md`, if present;
- `docs/PHASE_0_GAP_ANALYSIS.md`, if present;
- `docs/PROJECT_GUARDRAILS.md`, if present.

## Required Output File

Create or update:

```text
docs/DEVELOPMENT_SEQUENCE_BACKTEST_FIRST.md
```

## Required Document Structure

Use this structure:

```markdown
# Backtest-First Development Sequence

## 1. Purpose

This document defines the development order for the project.

The near-term target is:

1. complete historical data-based backtesting;
2. improve the score-based algorithm;
3. generate explainable order candidates;
4. provide decision logs;
5. require user review before any execution-related action.

Real account integration is intentionally deferred until the final stages.

## 2. Non-Negotiable Sequence Policy

Do not proceed to live execution until:

- backtest engine is implemented;
- score logic is testable;
- account constraints are modeled;
- order candidates are constraint-filtered;
- user review workflow is defined;
- execution safety policy is explicitly approved.

## 3. Phase Overview

| Phase | Name | Goal | Output |
|---:|---|---|---|
| 0 | Repository baseline and guardrails | Establish safe baseline | Docs and status |
| 1 | Asset universe | Define tradable/investable universe | Config and tests |
| 2 | Account constraints | Define account rules | Constraint model |
| 3 | Data pipeline | Separate raw data and derived data | Reproducible data layer |
| 4 | Feature layer | Convert raw data to normalized features | Feature contracts |
| 5 | Score layer | Convert features to comparable scores | Score contracts |
| 6 | Backtest engine | Validate logic historically | Leakage-safe backtest |
| 7 | Macro regime engine | Produce regime score distribution | Regime distribution |
| 8 | Sector scoring engine | Score sectors/assets | Decomposable sector scores |
| 9 | Risk budget engine | Calculate risk budgets | Risk budget outputs |
| 10 | Allocation engine | Generate target ranges | Allocation targets |
| 11 | Rebalancing engine | Generate rebalance intensity | Rebalance candidates |
| 12 | Reporting/audit layer | Explain decisions | Decision logs |
| 13 | Order candidates | Generate candidate orders | Reviewable candidates |
| 14 | User-approved execution | Optional manual approval flow | User-approved execution only |
| 15 | Limited automatic execution | Consider only after validation | Optional future capability |

## 4. Phase Details

For each phase, document:

- objective;
- allowed changes;
- prohibited changes;
- required tests;
- completion criteria;
- next phase dependency.

### Phase 0 — Repository Baseline and Guardrails

Objective:
Establish safe documentation baseline.

Exit criteria:

- repository audit exists;
- guardrails exist;
- gap analysis exists;
- architecture map exists;
- test baseline exists.

### Phase 1 — Asset Universe

Objective:
Define investable assets and sectors in configuration, not hardcoded strategy logic.

Exit criteria:

- asset universe config exists;
- disabled-by-default example assets exist if real assets are not finalized;
- tests validate config schema.

### Phase 2 — Account Constraint Model

Objective:
Represent account constraints explicitly before allocation or order candidates depend on them.

Exit criteria:

- account type model exists;
- live execution remains disabled;
- constraint tests exist.

### Phase 3 — Data Pipeline

Objective:
Separate raw, feature, score, and decision data.

Exit criteria:

- raw data is preserved where practical;
- derived data is reproducible;
- data quality metadata is attached.

### Phase 4 — Feature Layer

Objective:
Convert raw data into normalized features.

Exit criteria:

- feature outputs have dates, source, quality metadata;
- no feature uses future data.

### Phase 5 — Score Layer

Objective:
Convert features into comparable scores.

Exit criteria:

- standard score output contract exists;
- scores include confidence, data quality, stability, and reason codes.

### Phase 6 — Backtest Engine

Objective:
Validate score, allocation, and rebalance logic historically without leakage.

Exit criteria:

- historical simulation works;
- metrics include CAGR, MDD, volatility, turnover, and cost-adjusted return;
- leakage checks exist.

### Phase 7+ — Strategy Engines

Objective:
Build macro, sector, risk, allocation, and rebalance engines only after backtest foundations exist.

## 5. One-Task Execution Rule

Development should proceed by one task at a time:

1. select current task from `DevelopPlans/STATUS.md`;
2. complete the task;
3. test;
4. fix if needed;
5. update status;
6. stop.

Do not automatically continue to the next task.

## 6. Commit Recommendation

Use one commit per completed task when possible.

Suggested format:

```text
phase0: add repository audit
phase0: add project guardrails
phase0: add gap analysis
```

## 7. Open Questions

| ID | Question | Why It Matters | Conservative Default |
|---|---|---|---|
| Q003-001 | | | |
```

## Implementation Steps

1. Read required references.
2. Create or update `docs/DEVELOPMENT_SEQUENCE_BACKTEST_FIRST.md`.
3. Ensure real account integration is explicitly deferred.
4. Ensure Phase 6 backtest comes before production strategy promotion.
5. Update `DevelopPlans/STATUS.md`.

## Test Command

This task does not require functional tests.

If markdown linting exists, run it.

Otherwise document:

```text
No test command was run because this task only creates development sequence documentation.
```

## Acceptance Criteria

This task is complete only if:

- [ ] `docs/DEVELOPMENT_SEQUENCE_BACKTEST_FIRST.md` exists;
- [ ] phase order is explicit;
- [ ] backtest-first policy is explicit;
- [ ] real account integration is deferred;
- [ ] one-task execution rule is included;
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
