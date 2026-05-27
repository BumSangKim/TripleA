# TASK_004 — Architecture Map

## Objective

Create an architecture map that connects the current repository structure to the target architecture defined by the master development guide.

This task should make it clear which current files belong to which layer, which layers are missing, and which future phases should address the gaps.

## Scope

Allowed changes:

- create or update `docs/ARCHITECTURE_MAP.md`;
- map existing modules/files to target architecture layers;
- identify missing layers;
- identify unclear ownership boundaries;
- document target data and decision flow.

Not allowed:

- moving files;
- renaming modules;
- refactoring architecture;
- changing imports;
- changing production behavior;
- adding strategy rules;
- adding execution behavior.

## Required References

Read before starting:

- `AGENTS.md`, if present;
- `MASTER_DEVELOPMENT_GUIDE.md`, if present;
- `DevelopPlans/STATUS.md`;
- `docs/PHASE_0_REPOSITORY_AUDIT.md`, if present;
- `docs/PHASE_0_GAP_ANALYSIS.md`, if present;
- `docs/DEVELOPMENT_SEQUENCE_BACKTEST_FIRST.md`, if present.

## Required Output File

Create or update:

```text
docs/ARCHITECTURE_MAP.md
```

## Required Document Structure

Use this structure:

```markdown
# Architecture Map

## 1. Target Architecture

The target decision flow is:

```text
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
```

## 2. Target Layer Responsibilities

| Layer | Responsibility |
|---|---|
| Data Layer | Collect, store, version, and validate raw data |
| Feature Layer | Convert raw data into normalized investment features |
| Score Layer | Convert features into comparable scores |
| Macro Regime Engine | Produce macro regime score distributions |
| Sector Scoring Engine | Score sectors/assets by attractiveness, risk, and confidence |
| Risk Budget Engine | Calculate portfolio-level and account-level risk budgets |
| Allocation Engine | Generate target allocation ranges and current target weights |
| Rebalancing Engine | Calculate rebalancing intensity and action candidates |
| Account Constraint Engine | Enforce hard account/legal/product constraints |
| Backtest Engine | Validate strategy logic historically without leakage |
| Execution Engine | Generate and validate order candidates; execute only if explicitly allowed |
| Reporting/Audit Layer | Store decision reasons, versions, warnings, and logs |

## 3. Current Repository Mapping

| Target Layer | Existing Files/Modules | Current Status | Needed Changes | Recommended Phase |
|---|---|---|---|---|
| Data Layer | | missing / partial / present / unknown | | Phase 3 |
| Feature Layer | | missing / partial / present / unknown | | Phase 4 |
| Score Layer | | missing / partial / present / unknown | | Phase 5 |
| Macro Regime Engine | | missing / partial / present / unknown | | Phase 7 |
| Sector Scoring Engine | | missing / partial / present / unknown | | Phase 8 |
| Risk Budget Engine | | missing / partial / present / unknown | | Phase 9 |
| Allocation Engine | | missing / partial / present / unknown | | Phase 10 |
| Rebalancing Engine | | missing / partial / present / unknown | | Phase 11 |
| Account Constraint Engine | | missing / partial / present / unknown | | Phase 2 |
| Backtest Engine | | missing / partial / present / unknown | | Phase 6 |
| Execution Engine | | missing / partial / present / unknown | | Phase 13+ |
| Reporting/Audit Layer | | missing / partial / present / unknown | | Phase 12 |

## 4. Current Observed Flow

Document the current actual flow based on repository inspection.

If unclear, write:

```text
Current flow is not fully clear from existing files. The unclear boundary is: ...
```

## 5. Target Interface Boundaries

Document expected boundaries:

### Data → Feature

Input:
- raw data;
- source metadata;
- as-of date;
- data quality fields.

Output:
- normalized feature values;
- feature metadata.

### Feature → Score

Input:
- feature values;
- feature quality metadata.

Output:
- normalized score;
- confidence;
- data quality;
- stability;
- reason codes.

### Score → Allocation

Input:
- macro score distribution;
- sector/asset scores;
- risk budget score;
- account constraints.

Output:
- target ranges;
- current target weights;
- adjustment intensity.

### Allocation → Rebalancing

Input:
- target weights;
- current weights;
- cash;
- costs;
- tax assumptions;
- constraints.

Output:
- rebalance intensity;
- action candidates.

### Rebalancing → Order Candidate

Input:
- rebalance candidates;
- account constraints;
- order constraints.

Output:
- reviewable order candidates only.

## 6. Missing or Ambiguous Boundaries

| Boundary | Issue | Risk | Recommended Follow-Up |
|---|---|---|---|
| | | | |

## 7. Architecture Risks

List risks such as:

- direct raw data to order path;
- strategy logic mixed with data collection;
- execution logic mixed with decision logic;
- hardcoded parameters;
- missing decision logs;
- missing account constraint layer;
- missing backtest separation.

## 8. Open Questions

| ID | Question | Why It Matters | Conservative Default |
|---|---|---|---|
| Q004-001 | | | |
```

## Implementation Steps

1. Read repository audit and gap analysis if available.
2. Inspect repository structure if needed.
3. Create or update `docs/ARCHITECTURE_MAP.md`.
4. Do not move or refactor files.
5. Update `DevelopPlans/STATUS.md`.

## Test Command

This task does not require functional tests.

If markdown linting exists, run it.

Otherwise document:

```text
No test command was run because this task only creates architecture documentation.
```

## Acceptance Criteria

This task is complete only if:

- [ ] `docs/ARCHITECTURE_MAP.md` exists;
- [ ] target architecture flow is documented;
- [ ] target layer responsibilities are documented;
- [ ] current files/modules are mapped to layers where possible;
- [ ] missing or ambiguous boundaries are listed;
- [ ] architecture risks are documented;
- [ ] no files are moved or refactored;
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
