# AGENTS.md

## Always Follow

- Read `MASTER_DEVELOPMENT_GUIDE.md` before modifying source code, tests, config, prompts, or workflow docs.
- Read `DevelopPlans/STATUS.md` before selecting a task.
- Treat `MASTER_DEVELOPMENT_GUIDE.md` as the canonical development guide even if `docs/` is removed or rebuilt.
- Do not recreate `docs/` as a parallel source of truth unless the user explicitly approves that policy change.
- Execute only one task per run.
- Do not proceed to the next task unless explicitly instructed by the user. If the user provides an explicit batch prompt, still complete and commit each task independently before moving on.
- Preserve existing behavior unless the task explicitly requires change.
- Prefer minimal safe changes.
- Do not change architecture composition unless the task is explicitly architecture work.
- Keep files as independent as reasonably possible.
- Add or update tests for every non-documentation behavior change, covering input-to-output behavior when applicable.
- Do not add live execution or real account order logic.
- If uncertain, use conservative behavior: `NO_ACTION`, `HOLD`, `REVIEW_REQUIRED`, or `RISK_REDUCE_ONLY`.
- Treat layered score-flow feedback work as contract/skeleton-only unless the task has explicit owner approval for activation.
- Do not wire `FeedbackSignal`, `DecisionStateSnapshot`, `FeedbackCollector`, `MacroDistributionAdapter`, or `DecisionOrchestrator` into allocation, rebalancing, order candidate, API default, backtest default, broker, KIS, or execution behavior without explicit approval and validation.

## Task Loop

For the selected task:

1. Read the task file.
2. Inspect relevant existing code.
3. Implement the minimal change.
4. Run the required test command.
5. If the test fails, diagnose and fix.
6. Repeat implementation and testing until:
   - acceptance criteria pass, or
   - the blocker is documented.
7. Update `DevelopPlans/STATUS.md`.
8. Stop.

If an explicit batch prompt requires multiple task files, repeat this loop for
each task and create the task's commit before starting the next task.

## Prompt Requirements

Codex prompt files must be executable one at a time and include:

- allowed scope and forbidden behavior;
- acceptance criteria;
- required validation commands;
- stop conditions;
- the loop: development execution -> test -> recursive completion -> commit.

## Current Architecture Notes

- Canonical guide/status files live at the repository root and under
  `DevelopPlans/`; do not depend on `docs/`.
- Layered score-flow feedback contracts live under `api/domain/` and
  `api/score_pipeline/`.
- Lower layers may emit feedback contracts, but must not call upper-layer
  concrete engines.
- Active strategy formulas, macro thresholds, bucket shifts, allocation,
  rebalancing, order candidate behavior, broker/KIS behavior, and execution
  behavior remain unchanged unless a dedicated approved task changes them.
