# MASTER_DEVELOPMENT_GUIDE.md

## Purpose

This is the canonical development guide for the TripleA repository.

Codex and any coding agent must read this file before modifying source code,
tests, configuration, task prompts, or workflow documents.

This file intentionally lives at the repository root so it remains valid even
if `docs/` is removed or rebuilt.

## Canonical References

- `MASTER_DEVELOPMENT_GUIDE.md`: canonical development principles.
- `AGENTS.md`: concise operational instructions for coding agents.
- `DevelopPlans/STATUS.md`: canonical progress and task status when present.
- `DevelopPlans/layered_score_flow_feedback/target_architecture_contract.md`:
  current layered score-flow feedback boundary when working in that area.
- Task prompt files: executable work units only; they must not override this guide.

Do not depend on `docs/` as the source of truth for development rules.

Do not recreate `docs/` as a parallel guide tree unless the user explicitly
approves that repository policy change. New planning, status, inventory, and
handoff material belongs under `DevelopPlans/` unless a task says otherwise.

## Non-Negotiable Investment System Rules

- No Threshold Switch.
- Use continuous Score Flow.
- Hard Constraints First.
- Backtest Before Execution.
- Explain Every Decision.
- Parameters are data, not hardcoded constants.
- Conservative fallback on uncertainty.
- No default automatic execution.
- Do not add live order execution, broker order submission, or real-account mutation unless the user explicitly authorizes a dedicated execution task.

## Development Principles

### 0. Preserve Architecture Unless the Task Is Architecture Work

If the task is not explicitly an architecture-structure improvement task, do not
change the architecture composition.

Each file should remain as independent as reasonably possible. Prefer small,
local, well-scoped files over broad cross-cutting edits. Do not introduce a new
top-level layer, framework, service boundary, or dependency direction unless the
task explicitly requires it.

When uncertain, preserve existing behavior and use conservative states such as
`NO_ACTION`, `HOLD`, `REVIEW_REQUIRED`, or `RISK_REDUCE_ONLY`.

### 1. Test the Full Input-to-Output Path

Every non-documentation change must include or update tests that verify the
affected behavior from input data collection or fixture ingestion through the
observable output.

Required validation shape:

```text
source input / fixture
-> adapter or loader
-> repository / storage boundary
-> snapshot or domain object
-> feature / score / decision behavior when applicable
-> API / report / UI-visible output when applicable
```

Do not accept tests that only check an isolated helper when the change affects a
pipeline, API, strategy decision, reporting output, or UI behavior.

### 2. Split Prompts Into Executable Units

Codex task prompts must be split into files that can be executed one at a time.

Each prompt file must have:

- a single clear objective;
- allowed files or boundaries;
- forbidden files or behaviors;
- acceptance criteria;
- required test commands;
- stop conditions for unclear business rules or architecture mismatch.

Do not bundle unrelated implementation tasks into one prompt.

### 3. Prompt Workflow Must Be Explicit

Every implementation prompt must enforce this loop:

```text
development execution
-> test
-> recursive completion
-> commit
```

Expanded loop:

1. Read this guide and `AGENTS.md`.
2. Read the current task file completely.
3. Inspect the relevant repository state before editing.
4. Implement only the current task scope.
5. Add or update the required tests.
6. Run the task's specified validation commands.
7. If validation fails, diagnose and fix only within the current task scope.
8. Repeat until tests pass or a blocker is clearly documented.
9. Check `git status --short`.
10. Commit only intentional, safe changes when the task requires a commit.

Do not continue to the next task while the current task is failing.

### 4. Architecture Changes Must Be Extensible

If an architecture change is truly required, prefer an extensible contract or
adapter boundary over direct coupling.

Architecture changes must:

- preserve existing public behavior unless the task explicitly changes it;
- avoid downstream imports of upstream implementation details;
- provide a clear contract, port, schema, or adapter where data crosses layers;
- include regression tests for the old behavior and contract tests for the new boundary;
- document the reason for the change in the task output or status file.

If the required architecture direction is unclear, stop and report the blocker
instead of inventing a structure.

### 5. Layered Score-Flow Feedback Boundary

The current score-flow feedback architecture is contract-first and
non-activating by default.

Allowed structure:

```text
Data
-> Feature
-> Score
-> Macro
-> Sector/Asset
-> Risk
-> Allocation
-> Rebalancing
-> Constraint
-> Order Candidate
-> Audit
```

Lower layers may emit explicit feedback artifacts, but they must not directly
call upper-layer implementations. Use domain or score-pipeline contracts such as
`FeedbackSignal`, `DecisionStateSnapshot`, `FeedbackCollector`,
`MacroDistributionAdapter`, and `DecisionOrchestrator` for review-only
traceability.

The layered feedback contracts and orchestrator skeleton are not production
activation approval. Any task that wires them into allocation, rebalancing,
order candidate generation, API defaults, backtest defaults, or UI behavior
must have explicit owner confirmation and backtest or walk-forward validation
before implementation.

Keep the following boundaries:

- Domain contracts must not import FastAPI, SQLite, `api.db`, or `api.features`.
- Score-pipeline orchestrators must not import concrete strategy allocators,
  feature repositories, broker/KIS modules, or execution paths.
- Macro distribution adapter work may characterize existing macro behavior, but
  must not change macro thresholds, bucket shifts, allocation defaults, or
  rebalancing behavior.
- Feedback may recommend only conservative/review states:
  `NO_ACTION`, `HOLD`, `REVIEW_REQUIRED`, or `RISK_REDUCE_ONLY`.

## Forbidden Shortcuts

- Do not turn account constraints into score penalties only.
- Do not let downstream modules ignore hard constraints.
- Do not connect feature values directly to buy/sell decisions.
- Do not optimize parameters by historical return alone.
- Do not create order candidates in tasks that are not explicitly about order candidates.
- Do not touch broker, KIS, live execution, or account mutation paths unless the task explicitly permits it.
- Do not hardcode strategy parameters in source code when config or parameter files are the existing pattern.

## Completion Standard

A task is complete only when:

- the requested behavior is implemented within scope;
- relevant tests pass;
- no forbidden behavior was added;
- `git status --short` has been reviewed;
- remaining risks or `REVIEW_REQUIRED` items are documented;
- the next task is not started unless explicitly requested.
