# TASK_002 — Gap Analysis Against Master Development Guide

## Objective

Compare the current repository state against `MASTER_DEVELOPMENT_GUIDE.md` and document the gaps that must be resolved before the project can safely proceed to backtest-first algorithm development.

This task must use observations from the repository audit if available.

## Scope

Allowed changes:

- create or update `docs/PHASE_0_GAP_ANALYSIS.md`;
- classify current gaps by project area;
- assign recommended future phase for each gap;
- identify safety-critical gaps;
- document unknowns as open questions.

Not allowed:

- implementing missing modules;
- modifying strategy logic;
- modifying broker/API behavior;
- changing tests except documentation-related checks;
- making broad refactors;
- inventing business rules.

## Required References

Read before starting:

- `AGENTS.md`, if present;
- `MASTER_DEVELOPMENT_GUIDE.md`, if present;
- `DevelopPlans/STATUS.md`;
- `docs/PHASE_0_REPOSITORY_AUDIT.md`, if present;
- `docs/PROJECT_GUARDRAILS.md`, if present.

## Required Output File

Create or update:

```text
docs/PHASE_0_GAP_ANALYSIS.md
```

## Required Document Structure

Use this structure:

```markdown
# Phase 0 Gap Analysis Against MASTER_DEVELOPMENT_GUIDE

## 1. Summary

State whether the repository is ready for backtest-first development.

Use one of:

- Ready with minor documentation gaps;
- Partially ready;
- Not ready;
- Unknown due to insufficient repository information.

## 2. Critical Safety Gaps

List any gaps that could cause unsafe behavior, such as:

- live execution enabled by default;
- raw indicators mapped directly to orders;
- missing account constraint checks;
- missing backtest leakage prevention;
- hardcoded target weights;
- unexplained buy/sell logic.

## 3. Gap Table

| Area | Current State | Required State | Gap | Risk | Recommended Phase |
|---|---|---|---|---|---|
| Asset Universe | | Config-driven universe | | | Phase 1 |
| Account Constraints | | Explicit account model | | | Phase 2 |
| Data Pipeline | | Raw/feature/score separation | | | Phase 3 |
| Feature Layer | | Normalized features | | | Phase 4 |
| Score Layer | | Comparable score outputs | | | Phase 5 |
| Backtest Engine | | Leakage-safe backtest | | | Phase 6 |
| Macro Regime Engine | | Regime distribution | | | Phase 7 |
| Sector Scoring | | Decomposable sector score | | | Phase 8 |
| Risk Budget | | Portfolio/account risk budget | | | Phase 9 |
| Allocation | | Target ranges and gradual changes | | | Phase 10 |
| Rebalancing | | Rebalancing intensity | | | Phase 11 |
| Reporting/Audit | | Decision logs and reason codes | | | Phase 12 |
| Order Candidates | | Constraint-filtered candidates | | | Phase 13 |
| Execution | | User-approved only | | | Later |

## 4. Prohibited Pattern Check

| Prohibited Pattern | Found? | Location | Required Follow-Up |
|---|---:|---|---|
| Hardcoded strategy parameters | | | |
| Single-threshold regime switching | | | |
| Boolean-driven buy/sell logic | | | |
| Live strategy logic without backtesting | | | |
| Future-data leakage risk | | | |
| Ignoring account constraints | | | |
| Signals without data quality checks | | | |
| Unexplained buy/sell decisions | | | |
| Mapping raw data directly to orders | | | |
| Default automatic order execution | | | |

## 5. Recommended Development Priority

Keep the order aligned to the master guide:

1. Define asset universe.
2. Define account constraint model.
3. Build data pipeline.
4. Build feature layer.
5. Build score layer.
6. Build backtest engine.
7. Build macro regime engine.
8. Build sector scoring engine.
9. Build risk budget engine.
10. Build allocation engine.
11. Build rebalancing engine.
12. Build reporting/audit layer.
13. Generate order candidates.
14. Add user-approved execution only.
15. Consider limited automatic execution only after all safety requirements are met.

## 6. Open Questions

| ID | Question | Why It Matters | Conservative Default |
|---|---|---|---|
| Q002-001 | | | |
```

## Implementation Steps

1. Read repository audit and guardrails if available.
2. Compare current state against the master guide.
3. Fill the gap table.
4. Mark unknowns explicitly instead of guessing.
5. Create or update `docs/PHASE_0_GAP_ANALYSIS.md`.
6. Update `DevelopPlans/STATUS.md`.

## Test Command

This task does not require functional tests.

If markdown linting exists, run it.

Otherwise document:

```text
No test command was run because this task only creates gap analysis documentation.
```

## Acceptance Criteria

This task is complete only if:

- [ ] `docs/PHASE_0_GAP_ANALYSIS.md` exists;
- [ ] gap table is filled with current state, required state, gap, risk, and recommended phase;
- [ ] critical safety gaps are listed;
- [ ] prohibited pattern check is included;
- [ ] unknowns are documented instead of guessed;
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
