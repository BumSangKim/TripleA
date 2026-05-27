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

Existing read-only broker/account sync may remain available for account snapshot visibility, but it must not become position-changing behavior during early phases.

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

For each phase, future task files should document:

- objective;
- allowed changes;
- prohibited changes;
- required tests;
- completion criteria;
- next phase dependency.

### Phase 0 — Repository Baseline and Guardrails

Objective:
Establish safe documentation baseline.

Allowed changes:

- repository audit;
- project guardrails;
- gap analysis;
- development sequence;
- architecture map;
- test baseline.

Prohibited changes:

- production strategy behavior changes;
- broker execution changes;
- account-linked order submission;
- broad refactors.

Required tests:

- documentation checks if available;
- baseline test run for `TASK_005`.

Exit criteria:

- repository audit exists;
- guardrails exist;
- gap analysis exists;
- architecture map exists;
- test baseline exists;
- canonical status is updated.

Next phase dependency:
Phase 1 can begin only after Phase 0 documents make current gaps and safety boundaries visible.

### Phase 1 — Asset Universe

Objective:
Define investable assets and sectors in configuration, not hardcoded strategy logic.

Allowed changes:

- asset universe schema;
- disabled-by-default placeholder assets if final universe is not approved;
- tests for asset metadata.

Prohibited changes:

- new allocation behavior based on unapproved assets;
- live trading enablement.

Required tests:

- config loading tests;
- schema validation tests;
- conservative fallback tests for invalid assets.

Exit criteria:

- asset universe config exists;
- disabled-by-default example assets exist if real assets are not finalized;
- tests validate config schema.

Next phase dependency:
Account constraints must know which assets and products can be evaluated.

### Phase 2 — Account Constraint Model

Objective:
Represent account constraints explicitly before allocation or order candidates depend on them.

Allowed changes:

- account type model;
- product eligibility model;
- hard constraint validation contracts.

Prohibited changes:

- broker order placement;
- automatic retries;
- silent candidate execution.

Required tests:

- account type restrictions;
- risky-asset limits;
- missing account data fallback;
- product eligibility rejection.

Exit criteria:

- account type model exists;
- live execution remains disabled;
- constraint tests exist.

Next phase dependency:
Data and strategy layers must be able to consume constraints without embedding account rules inside allocation logic.

### Phase 3 — Data Pipeline

Objective:
Separate raw, feature, score, and decision data.

Allowed changes:

- raw data storage contracts;
- source metadata;
- as-of date and quality metadata;
- reproducible fetch/import behavior.

Prohibited changes:

- direct raw-data-to-order mapping;
- strategy promotion based only on newly fetched data.

Required tests:

- source metadata preservation;
- stale/missing data detection;
- reproducibility checks where practical.

Exit criteria:

- raw data is preserved where practical;
- derived data is reproducible;
- data quality metadata is attached.

Next phase dependency:
Feature calculation must consume stable, quality-scored data inputs.

### Phase 4 — Feature Layer

Objective:
Convert raw data into normalized features.

Allowed changes:

- feature contracts;
- normalization logic;
- release-date awareness;
- data quality propagation.

Prohibited changes:

- raw indicator thresholds becoming buy/sell decisions;
- features using future data.

Required tests:

- feature date alignment;
- normalization bounds;
- missing/stale data fallback.

Exit criteria:

- feature outputs have dates, source, quality metadata;
- no feature uses future data.

Next phase dependency:
Score layer must consume comparable feature outputs.

### Phase 5 — Score Layer

Objective:
Convert features into comparable scores.

Allowed changes:

- standard score output schema;
- confidence and data-quality scoring;
- reason-code generation.

Prohibited changes:

- score thresholds directly forcing allocation changes;
- unversioned parameter changes.

Required tests:

- score output contract;
- confidence/data quality behavior;
- conservative fallback on missing inputs.

Exit criteria:

- standard score output contract exists;
- scores include confidence, data quality, stability, and reason codes.

Next phase dependency:
Backtests must evaluate score outputs rather than raw signal shortcuts.

### Phase 6 — Backtest Engine

Objective:
Validate score, allocation, and rebalance logic historically without leakage.

Allowed changes:

- leakage-safe simulation;
- cost, tax, turnover, and drawdown metrics;
- reproducible historical data snapshots;
- benchmark and sensitivity reporting.

Prohibited changes:

- promoting a strategy only because of high historical return;
- using future/revised data as if known historically.

Required tests:

- simulation mechanics;
- as-of data use;
- cost/slippage/tax effects;
- failure on insufficient data.

Exit criteria:

- historical simulation works;
- metrics include CAGR, MDD, volatility, turnover, and cost-adjusted return;
- leakage checks exist.

Next phase dependency:
Strategy engines should be improved against a reliable backtest harness.

### Phase 7 — Macro Regime Engine

Objective:
Produce macro regime score distributions, not single-label switches.

Exit criteria:

- regime distribution exists;
- confidence and data quality are included;
- allocation consumes the distribution gradually.

### Phase 8 — Sector Scoring Engine

Objective:
Score sectors/assets with decomposable reasons.

Exit criteria:

- sector scores include macro fit, momentum, valuation/risk where available, confidence, and data quality;
- missing inputs produce hold/review behavior.

### Phase 9 — Risk Budget Engine

Objective:
Calculate portfolio and account-level risk budgets.

Exit criteria:

- portfolio bucket budgets and account-level constraints are reconciled;
- risk budgets are explainable and testable.

### Phase 10 — Allocation Engine

Objective:
Generate target ranges and current target weights.

Exit criteria:

- allocation changes are gradual;
- turnover, tax, cost, confidence, and constraints are considered;
- outputs include explanations and versions.

### Phase 11 — Rebalancing Engine

Objective:
Generate rebalancing intensity and reviewable action candidates.

Exit criteria:

- rebalance intensity score exists;
- small/noisy deviations can result in `HOLD`;
- costs and constraints are considered.

### Phase 12 — Reporting/Audit Layer

Objective:
Explain every decision.

Exit criteria:

- decision logs include inputs, scores, constraints, versions, warnings, and reason codes;
- reports are reproducible.

### Phase 13 — Order Candidates

Objective:
Generate reviewable candidate orders only after constraints.

Exit criteria:

- candidates are account/product/order constrained;
- no broker submission occurs;
- user review output is clear.

### Phase 14 — User-Approved Execution

Objective:
Consider optional manual approval flow only after prior phases.

Exit criteria:

- explicit user approval is required;
- broker/API behavior is validated in paper or sandbox mode;
- live execution is separately approved.

### Phase 15 — Limited Automatic Execution

Objective:
Consider only after validation and explicit approval.

Exit criteria:

- this phase remains optional;
- all safety, audit, rollback, monitoring, and approval requirements are met.

## 5. One-Task Execution Rule

Development should proceed by one task at a time:

1. select current task from `DevelopPlans/STATUS.md`;
2. complete the task;
3. test;
4. fix if needed;
5. update status;
6. stop.

Do not automatically continue to the next task unless the user explicitly authorizes a multi-task run, as happened for completion of Phase 0.

## 6. Commit Recommendation

Use one commit per completed task when possible.

Suggested format:

```text
phase0: add repository audit
phase0: add project guardrails
phase0: add gap analysis
phase0: add backtest-first sequence
phase0: add architecture map
phase0: add test baseline
```

## 7. Open Questions

| ID | Question | Why It Matters | Conservative Default |
|---|---|---|---|
| Q003-001 | Should the existing partial backtest engine be treated as Phase 6 complete or as a foundation to harden in Phase 6? | Determines whether future work is cleanup or new implementation. | Treat as partial and require leakage/reproducibility hardening. |
| Q003-002 | Which Phase 1 asset universe should be approved first: current default global universe or a smaller disabled-by-default universe? | Affects downstream account constraints and backtest coverage. | `REVIEW_REQUIRED` before adding risk exposure. |
| Q003-003 | Should real broker read-only sync remain in early phases? | It can help dashboards but increases operational sensitivity. | Allow read-only sync only; no position-changing behavior. |
| Q003-004 | How should task files be normalized between `docs/phase0/` and logical `DevelopPlans/phase0/` paths? | Prevents future automation from reading stale paths. | Use `DevelopPlans/STATUS.md` as canonical status and avoid moving task files without approval. |

