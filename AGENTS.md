# AGENTS.md

## Always Follow

- Read `MASTER_DEVELOPMENT_GUIDE.md` before strategy-related changes.
- Read `DevelopPlans/STATUS.md` before selecting a task.
- Execute only one task per run.
- Do not proceed to the next task unless explicitly instructed by the user.
- Preserve existing behavior unless the task explicitly requires change.
- Prefer minimal safe changes.
- Add or update tests when changing strategy logic.
- Do not add live execution or real account order logic.
- If uncertain, use conservative behavior: `NO_ACTION`, `HOLD`, `REVIEW_REQUIRED`, or `RISK_REDUCE_ONLY`.

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