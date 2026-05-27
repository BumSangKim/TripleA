# Account Constraint Engine Specification

## Purpose

The account constraint engine defines hard account, product, cash, sizing, and audit rules that must be evaluated before downstream allocation changes, rebalancing actions, or order candidates can be considered actionable.

Scores cannot override constraints. A high investment score may explain attractiveness, but it must not permit an action that violates an account constraint.

## Non-Goals

- No live order execution.
- No automatic order execution.
- No broker API order submission.
- No allocation optimization or score penalty model.
- No broad rewrite of existing dashboard, provider, rebalancing, order, or backtest modules.

## Supported Account Types

The supported account types are:

- `taxable`
- `isa`
- `pension`
- `irp`

Unknown account types must not be interpreted as buy-eligible. They must return `REVIEW_REQUIRED` or `NO_ACTION`.

## Account Role Model

Account roles are configuration metadata, not immutable strategy truth. Initial roles include:

- `aggressive_growth`
- `tax_efficient_growth`
- `long_term_growth`
- `defensive_growth`

If a user or future approved configuration defines a different account role, that reviewed configuration takes priority. If role metadata is missing or unclear, the conservative fallback is `REVIEW_REQUIRED`.

## Hard Constraint Definition

A hard constraint is a rule that blocks, reduces, or marks an action for review before it can become an actionable candidate.

Examples include:

- account type unknown;
- product not tradable in account;
- IRP risky asset limit exceeded;
- leveraged, inverse, or futures-like product restricted;
- insufficient cash;
- minimum order unit not satisfied;
- market halted, suspended, or delisted;
- missing balance or position data;
- API state unknown.

Hard constraints must not be softened into scores.

## Constraint Evaluation Order

Rules must be evaluated in this order:

1. Data completeness.
2. Account eligibility.
3. Product eligibility.
4. Account-specific limits.
5. Cash and order sizing.
6. Review and audit packaging.

When multiple rules fail, the result should accumulate all reason codes rather than returning only the first issue.

## Constraint Result Contract

Every evaluation returns a result with these fields:

- `allowed`: boolean.
- `action`: one of `ALLOW`, `BLOCK`, `REDUCE_ONLY`, `REVIEW_REQUIRED`, `NO_ACTION`, `HOLD`, `RISK_REDUCE_ONLY`.
- `severity`: one of `info`, `warning`, `review`, `block`.
- `constraint_type`: stable category such as `data_completeness`, `account_eligibility`, `product_eligibility`, `account_limit`, `cash_sizing`, or `audit`.
- `reason_codes`: list of stable reason codes.
- `warnings`: list of non-blocking warnings.
- `blocked_fields`: list of fields that blocked or constrained the result.
- `adjusted_quantity`: optional conservative quantity after reduction.
- `adjusted_weight`: optional conservative target weight after reduction.
- `review_required`: boolean.
- `audit`: deterministic audit payload.

## Reason Code Taxonomy

Initial reason codes:

- `UNKNOWN_ACCOUNT_TYPE`
- `MISSING_ACCOUNT_CONFIG`
- `MISSING_ACCOUNT_STATE`
- `MISSING_BALANCE`
- `MISSING_POSITION_VALUATION`
- `MISSING_PRODUCT_METADATA`
- `PRODUCT_NOT_TRADABLE`
- `ASSET_CLASS_NOT_ALLOWED`
- `PRODUCT_FLAG_RESTRICTED`
- `IRP_RISKY_ASSET_LIMIT_EXCEEDED`
- `IRP_RISKY_ASSET_DATA_MISSING`
- `INSUFFICIENT_CASH`
- `MIN_ORDER_UNIT_NOT_SATISFIED`
- `MARKET_NOT_TRADABLE`
- `API_STATE_UNKNOWN`
- `INVALID_CONSTRAINT_CONFIG`

Reason codes are explanatory and must not be used as score penalties.

## Conservative Fallback Policy

For unknown, missing, malformed, stale, or API-dependent data, the default result must be one of:

- `NO_ACTION`
- `HOLD`
- `REVIEW_REQUIRED`
- `RISK_REDUCE_ONLY`

The fallback must not permit a buy, risk increase, or forced rebalance.

## Backtest Compatibility

The engine must be callable with only deterministic inputs:

- account config;
- account state as of a date;
- product metadata as of a date;
- portfolio or position state;
- order or allocation intent.

It must not read the current time, query a broker, call external APIs, or depend on live account state.

Example:

```python
result = evaluate_account_constraints(
    account_config=account_config,
    account_state=account_state_as_of_date,
    product=product_metadata_as_of_date,
    intent=backtest_order_or_allocation_intent,
)
```

The same inputs must return the same `ConstraintResult` and audit payload.

## Order Candidate Compatibility

Order candidate generation may consume constraint results in future phases. A candidate is actionable only when `allowed=true`, `review_required=false`, and the action is `ALLOW`.

If the result is `BLOCK`, `NO_ACTION`, `REVIEW_REQUIRED`, `HOLD`, `REDUCE_ONLY`, or `RISK_REDUCE_ONLY`, downstream code must not silently treat the candidate as executable.

## Audit Payload Contract

The audit payload must include:

- `account_type`;
- `account_role`;
- `product_id` or `symbol`;
- `intent_type`;
- `requested_quantity` or `requested_weight`;
- `adjusted_quantity` or `adjusted_weight`;
- `allowed`;
- `action`;
- `severity`;
- `reason_codes`;
- `warnings`;
- `evaluated_rules`;
- `as_of_date`;
- `config_version` or `parameter_version` when available.

Audit payloads must be deterministic for identical inputs.
