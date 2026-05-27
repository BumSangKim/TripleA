# Reporting And Audit Specification

The reporting and audit layer records machine-readable decisions and explains outcomes using stored traces, reason codes, warnings, and version metadata.

## Decision Log

Each decision log entry includes:

- decision date;
- data snapshot ID;
- parameter version;
- model version;
- macro scores;
- sector scores;
- risk budget scores;
- target weights;
- current weights;
- rebalance scores;
- account constraints;
- decision result;
- adjustment intensity;
- reason codes;
- warnings.

Sensitive account identifiers must be masked or omitted. Logs are reproducible and serializable.

## Reason Codes And Warnings

Reason codes are stable strings grouped by data quality, macro regime, sector score, risk budget, allocation, rebalancing, account constraint, order candidate, and fallback categories. Warnings carry source module and severity.

## Backtest Reports

Reports include available return/risk metrics, turnover, cost/tax-adjusted return fields, stress/regime placeholders when unavailable, parameter/model versions, warnings, and an explicit historical-review statement. Unsupported metrics are marked unavailable rather than silently omitted.

## Explanation Service

Explanations are derived from decision logs. If a decision log entry is missing, the response is unavailable rather than invented.

