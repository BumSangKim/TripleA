# Phase 1 Asset Universe Guardrails

## 1. Purpose

This document defines Phase 1 guardrails for asset universe definition.

Phase 1 creates a configurable, testable, account-aware, score-compatible foundation for assets. It does not implement investment decisions, allocation behavior, rebalancing behavior, broker-linked trading, or execution.

## 2. Phase 1 Scope

Allowed outputs:

- asset universe schema;
- asset metadata model;
- asset universe configuration;
- universe loader;
- universe validation logic;
- sector and asset class mapping metadata;
- account eligibility metadata;
- data requirement metadata;
- universe snapshot export;
- tests and documentation;
- conservative validation failures for missing or unclear metadata.

Out of scope:

- live execution;
- broker order submission;
- account-linked automatic execution;
- automatic buying or selling;
- hardcoded strategy weights;
- threshold-driven investment decisions;
- macro regime engine implementation;
- allocation engine implementation;
- rebalancing engine implementation;
- order candidate execution.

## 3. Non-Negotiable Boundaries

Phase 1 must preserve these boundaries:

- define asset universe only;
- no live execution;
- no broker order submission;
- no hardcoded strategy weights;
- no raw-data-to-order shortcut;
- no single-threshold buy/sell logic;
- no default risk-increasing behavior.

If a later task needs a placeholder for missing investment or business rules, use a conservative state such as:

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

## 4. Asset Metadata Expectations

Asset universe records should be explicit and reviewable.

Expected metadata areas include:

- stable asset identifier;
- display name;
- asset class;
- sector or category where applicable;
- region or market;
- currency;
- data source requirements;
- account eligibility metadata;
- enabled or disabled status;
- review status or conservative fallback marker when unclear.

Missing required metadata must fail validation conservatively. It must not be silently interpreted as eligible, tradable, or risk-increasing.

## 5. Account Eligibility Policy

Account eligibility in Phase 1 is metadata only.

It may describe whether an asset is eligible, ineligible, unknown, or review-required for account types. It must not submit orders or connect to live accounts.

If eligibility is missing or unclear, the conservative default is:

```text
REVIEW_REQUIRED
```

## 6. Configuration Policy

The asset universe must be configuration-driven.

Do not embed future asset additions directly inside strategy logic. Adding, disabling, or reviewing an asset should normally require configuration and tests, not allocation code changes.

## 7. Testing Policy

Every non-trivial Phase 1 behavior must have tests.

Tests should cover:

- valid universe records;
- missing required metadata;
- disabled assets;
- unknown account eligibility;
- invalid sector or asset class mappings;
- snapshot/export shape when introduced;
- conservative failure behavior.

## 8. Documentation Policy

Each Phase 1 task must update `docs/PHASE_1_STATUS.md` with:

- completed task number;
- major files created or modified;
- test command run;
- test result;
- remaining TODO or `REVIEW_REQUIRED` items;
- next task.

