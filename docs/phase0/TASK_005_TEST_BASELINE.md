# TASK_005 — Test Baseline

## Objective

Run the current repository's existing tests or identify why tests cannot be run, then document the baseline result.

This task establishes the test baseline before future backtest, score, allocation, and constraint logic is implemented.

## Scope

Allowed changes:

- create or update `docs/PHASE_0_TEST_BASELINE.md`;
- inspect test configuration;
- run existing tests;
- document failures;
- document missing test areas;
- optionally fix only trivial documentation/test invocation issues if clearly safe.

Not allowed:

- broad test framework migration;
- changing production logic to force tests to pass;
- changing strategy behavior;
- adding new investment rules;
- adding broker execution;
- enabling live execution;
- ignoring failing tests;
- hiding test failures.

## Required References

Read before starting:

- `AGENTS.md`, if present;
- `MASTER_DEVELOPMENT_GUIDE.md`, if present;
- `DevelopPlans/STATUS.md`;
- `docs/PHASE_0_REPOSITORY_AUDIT.md`, if present;
- existing test files;
- package manager files such as `pyproject.toml`, `requirements.txt`, `package.json`, `Makefile`, or CI configs.

## Required Output File

Create or update:

```text
docs/PHASE_0_TEST_BASELINE.md
```

## Required Document Structure

Use this structure:

```markdown
# Phase 0 Test Baseline

## 1. Test Environment

- Date:
- OS/environment:
- Language/runtime version:
- Package manager:
- Test framework:
- Dependency installation command used:

## 2. Test Discovery

| Source | Finding |
|---|---|
| Test directory | |
| Test config | |
| CI config | |
| Makefile/script | |

## 3. Test Command Used

```bash
<command>
```

If no test command can be determined, write:

```text
No reliable test command was found.
```

## 4. Result

Use one of:

- Passed;
- Failed;
- Could not run;
- Not applicable because no tests exist.

## 5. Failure Summary

If tests failed, document:

| Test/Command | Failure Summary | Likely Cause | Related to This Task? |
|---|---|---|---|
| | | | |

Do not hide or over-fix failures.

## 6. Missing Test Areas

Check whether tests exist for:

| Area | Test Exists? | Notes |
|---|---:|---|
| Data cleaning | | |
| Feature calculation | | |
| Score calculation | | |
| Regime distribution calculation | | |
| Sector scoring | | |
| Risk budget calculation | | |
| Target allocation calculation | | |
| Rebalancing score calculation | | |
| Account constraint validation | | |
| Order candidate generation | | |
| Backtest simulation | | |
| Future-data leakage prevention | | |
| Parameter loading and versioning | | |
| Conservative fallback behavior | | |

## 7. Recommended Next Test Work

List specific future test tasks, but do not implement them in this task.

## 8. Open Questions

| ID | Question | Why It Matters | Conservative Default |
|---|---|---|---|
| Q005-001 | | | |
```

## Implementation Steps

1. Inspect test-related files.
2. Determine the safest existing test command.
3. Run the test command.
4. If dependencies are missing, document the missing dependency and command attempted.
5. If tests fail, determine whether failures are pre-existing or caused by this task.
6. Do not change production logic.
7. Create or update `docs/PHASE_0_TEST_BASELINE.md`.
8. Update `DevelopPlans/STATUS.md`.

## Preferred Test Commands

If Python project:

```bash
pytest
```

If package scripts exist:

```bash
npm test
```

or

```bash
make test
```

Use the repository's own documented command if available.

## Acceptance Criteria

This task is complete only if:

- [ ] `docs/PHASE_0_TEST_BASELINE.md` exists;
- [ ] test discovery is documented;
- [ ] command used is documented;
- [ ] test result is documented;
- [ ] failures are summarized if present;
- [ ] missing test areas are listed;
- [ ] no production logic is changed to force test success;
- [ ] no live execution logic is added;
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
