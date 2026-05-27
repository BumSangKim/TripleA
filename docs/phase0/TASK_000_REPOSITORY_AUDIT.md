# TASK_000 — Repository Audit

## Objective

Inspect the current repository and document the existing structure, execution flow, investment-related logic, and risk areas.

This task is a documentation and baseline task only. It must not change strategy behavior.

## Scope

Allowed changes:

- create or update `docs/PHASE_0_REPOSITORY_AUDIT.md`;
- inspect repository files and directories;
- document existing modules and current execution flow;
- classify current strategy logic as score-based, threshold-based, hardcoded, unknown, or not investment logic;
- document risk areas and unclear points.

Not allowed:

- changing production logic;
- changing allocation, scoring, backtest, broker, or execution behavior;
- deleting existing code;
- adding new strategy rules;
- adding live execution behavior.

## Required References

Read before starting:

- `AGENTS.md`, if present;
- `MASTER_DEVELOPMENT_GUIDE.md`, if present;
- `DevelopPlans/STATUS.md`;
- repository README or existing documentation;
- existing test configuration files.

## Required Output File

Create or update:

```text
docs/PHASE_0_REPOSITORY_AUDIT.md
```

## Required Document Structure

Use this structure:

```markdown
# Phase 0 Repository Audit

## 1. Repository Summary

- Main language:
- Package manager:
- Test framework:
- Entry points:
- Data storage:
- Existing broker/API modules:
- Existing backtest modules:
- Existing allocation/scoring modules:
- Existing reporting/logging modules:

## 2. Directory Map

| Path | Observed Purpose | Notes |
|---|---|---|
| | | |

## 3. Important Files

| File | Observed Role | Investment-Relevant? | Notes |
|---|---|---:|---|
| | | | |

## 4. Current Execution Flow

Describe the observed flow.

Expected target reference:

Raw data
→ preprocessing / feature generation
→ score calculation
→ allocation / decision
→ report / candidate output
→ execution only if explicitly enabled later

If the actual flow is unclear, state exactly where it is unclear.

## 5. Existing Strategy Logic

| Location | Logic Summary | Classification | Risk |
|---|---|---|---|
| | | score-based / threshold-based / hardcoded / unknown / not investment logic | |

## 6. Existing Backtest Capability

- Backtest entry point:
- Data assumptions:
- Output metrics:
- Leakage protection observed:
- Current limitations:

## 7. Existing Execution or Broker API Capability

- Broker/API files:
- Order-related functions:
- Mock/paper trading behavior:
- Real trading behavior:
- Safety concerns:

## 8. Current Risk Areas

Check for violations of:

- Score Flow;
- Hard Constraints First;
- Backtest Before Execution;
- no automatic execution by default;
- no hardcoded strategy parameters;
- no future-data leakage;
- explainability requirement;
- conservative fallback behavior.

## 9. Open Questions

| ID | Question | Why It Matters | Conservative Default |
|---|---|---|---|
| Q000-001 | | | |
```

## Implementation Steps

1. Inspect the repository root.
2. Identify language, package manager, test framework, and entry points.
3. Inspect likely files for data collection, scoring, allocation, backtesting, broker/API, configuration, and reporting.
4. Do not edit code.
5. Create or update `docs/PHASE_0_REPOSITORY_AUDIT.md`.
6. Run a non-invasive check if available, such as listing tests or reading test config.
7. Update `DevelopPlans/STATUS.md`.

## Test Command

This task does not require functional code tests.

If the repository has markdown linting or documentation checks, run the relevant command.

If no documentation test exists, document:

```text
No test command was run because this task only creates repository audit documentation.
```

## Acceptance Criteria

This task is complete only if:

- [ ] `docs/PHASE_0_REPOSITORY_AUDIT.md` exists;
- [ ] repository structure is documented;
- [ ] existing investment logic is classified;
- [ ] broker/API and execution-related files are identified if present;
- [ ] current backtest capability is described if present;
- [ ] risk areas are documented;
- [ ] open questions are documented;
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
