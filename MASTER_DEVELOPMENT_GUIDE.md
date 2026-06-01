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
- Task prompt files: executable work units only; they must not override this guide.

Do not depend on `docs/` as the source of truth for development rules.

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
