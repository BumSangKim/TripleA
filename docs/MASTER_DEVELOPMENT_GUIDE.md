# MASTER_DEVELOPMENT_GUIDE.md

## 0. Document Purpose

This document is the master development guide for the investment automation project.

It defines the architectural philosophy, decision principles, scoring contract, risk rules, data rules, account constraints, backtest requirements, and execution boundaries for the system.

This is not a detailed implementation specification for one module.
It is the parent guide that all detailed specifications must follow.

Related documents should be created under `docs/` and must not violate this guide:

```text
docs/
  PROJECT_GUARDRAILS.md
  DATA_PIPELINE_SPEC.md
  FEATURE_LAYER_SPEC.md
  SCORE_LAYER_SPEC.md
  MACRO_REGIME_ENGINE_SPEC.md
  SECTOR_SCORING_ENGINE_SPEC.md
  RISK_BUDGET_ENGINE_SPEC.md
  ALLOCATION_ENGINE_SPEC.md
  REBALANCING_ENGINE_SPEC.md
  ACCOUNT_CONSTRAINT_ENGINE_SPEC.md
  BACKTEST_ENGINE_SPEC.md
  EXECUTION_ENGINE_SPEC.md
  REPORTING_AUDIT_SPEC.md
```

The concise operational instruction file for Codex is `AGENTS.md`.
This document is the expanded source of truth for architectural decisions.

---

# 1. System Identity

## 1.1 What This System Is

This system is a score-based dynamic asset allocation engine.

It uses macro data, market data, sector data, company metrics, risk metrics, account constraints, and portfolio state to generate:

- macro regime score distributions;
- sector and asset attractiveness scores;
- account-aware risk budgets;
- target allocation ranges;
- current target weights;
- rebalancing intensity;
- order candidates;
- decision explanations;
- audit logs.

The system must be explainable, testable, reproducible, and conservative under uncertainty.

---

## 1.2 What This System Is Not

This system is not:

- a short-term trading bot;
- a single-indicator rule engine;
- a threshold-based risk-on/risk-off switch;
- a fixed-weight allocation template;
- a black-box prediction model;
- an automatic order execution system by default;
- a system that optimizes historical return without risk, tax, cost, and account constraints.

---

## 1.3 Core Anchor

```text
No Threshold Switch.
Use Score Flow.
Hard Constraints First.
Backtest Before Execution.
Explain Every Decision.
```

Expanded anchor:

```text
This system does not abruptly buy, sell, or rotate assets because a single threshold was crossed.

It converts all relevant investment inputs into continuous, normalized, smoothed, confidence-adjusted scores.

Those scores flow through macro regime, sector scoring, risk budget, allocation, and rebalancing engines.

Only after score-based decisions pass hard account constraints and risk checks can order candidates be generated.
```

---

# 2. Top-Level Design Philosophy

## 2.1 Score Flow Instead of Threshold Switch

All investment decisions must be based on connected scores.

The system must not use rules like:

```python
if vix > 30:
    regime = "risk_off"
    equity_weight = 0.3
```

Instead, it should use a score flow:

```python
volatility_score = score_model.calculate_volatility_score(inputs)

risk_off_score = regime_model.calculate_risk_off_score(
    volatility_score=volatility_score,
    credit_score=credit_score,
    liquidity_score=liquidity_score,
    trend_score=trend_score,
)

target_weight = allocation_model.adjust_weight_gradually(
    base_weight=base_weight,
    risk_score=risk_off_score,
    confidence=confidence,
)
```

Thresholds may exist, but not as direct investment switches.

---

## 2.2 Gradual Transition

Market conditions do not usually change as clean binary states.
The system must treat macro regimes, sector attractiveness, risk budgets, and target weights as continuous variables.

Every transition should be gradual unless a hard constraint or emergency safety condition is triggered.

Required mechanisms:

- score normalization;
- score smoothing;
- confidence adjustment;
- data quality adjustment;
- allocation change limits;
- turnover limits;
- transaction cost checks;
- tax impact checks;
- account constraint checks.

---

## 2.3 Explainability Over Raw Optimization

The system should not select strategies or parameters only because they produce the highest backtest return.

A strategy must be rejected or downgraded if it is:

- unexplained;
- overfit;
- too sensitive to small parameter changes;
- dependent on one historical regime;
- dependent on future data leakage;
- too costly after transaction costs;
- ineffective after tax impact;
- incompatible with account constraints;
- operationally fragile.

---

# 3. Core Decision Flow

The required decision flow is:

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
→ User Review or Execution
```

No module may bypass this flow for strategy decisions.

Prohibited shortcuts:

```text
Raw Data → Buy/Sell
Single Indicator → Regime Switch
Dominant Regime Label → Fixed Weights
Sector Name → Hardcoded Weight
Backtest Return → Production Strategy
```

---

# 4. Module Architecture

## 4.1 Required Layers

The system should be organized around the following layers:

```text
Data Layer
Feature Layer
Score Layer
Macro Regime Engine
Sector Scoring Engine
Risk Budget Engine
Allocation Engine
Rebalancing Engine
Account Constraint Engine
Backtest Engine
Execution Engine
Reporting / Audit Layer
```

---

## 4.2 Layer Responsibilities

| Layer | Responsibility |
|---|---|
| Data Layer | Collect, store, version, and validate raw data |
| Feature Layer | Convert raw data into normalized investment features |
| Score Layer | Convert features into comparable scores |
| Macro Regime Engine | Produce macro regime score distributions |
| Sector Scoring Engine | Score sectors and assets by attractiveness, risk, and confidence |
| Risk Budget Engine | Calculate portfolio-level and account-level risk budgets |
| Allocation Engine | Generate target allocation ranges and current target weights |
| Rebalancing Engine | Calculate rebalancing intensity and action candidates |
| Account Constraint Engine | Enforce hard account/legal/product constraints |
| Backtest Engine | Validate strategy logic historically without leakage |
| Execution Engine | Generate and validate order candidates; execute only if allowed |
| Reporting / Audit Layer | Store decision reasons, versions, warnings, and logs |

---

## 4.3 Module Independence

Each module must expose outputs through documented contracts.
A downstream module should not depend on the internal implementation of an upstream module.

For example, the Allocation Engine should consume sector scores, not directly inspect how those scores were calculated.

Preferred interface:

```json
{
  "sector": "semiconductor",
  "total_score": 0.78,
  "macro_fit_score": 0.74,
  "industry_momentum_score": 0.81,
  "valuation_score": 0.55,
  "risk_penalty_score": 0.31,
  "confidence": 0.73,
  "data_quality": 0.91,
  "as_of_date": "YYYY-MM-DD"
}
```

---

# 5. Score-Based Design Contract

## 5.1 Standard Decision Output

Every major strategy module should produce a structure compatible with:

```json
{
  "score": 0.0,
  "previous_score": 0.0,
  "score_change": 0.0,
  "confidence": 0.0,
  "data_quality": 0.0,
  "stability": 0.0,
  "adjustment_intensity": 0.0,
  "reason_codes": [],
  "as_of_date": "YYYY-MM-DD",
  "parameter_version": "string",
  "model_version": "string"
}
```

---

## 5.2 Required Score Properties

Every score used for investment decisions should have:

| Property | Meaning |
|---|---|
| `score` | Current normalized score |
| `previous_score` | Prior score for change detection |
| `score_change` | Magnitude and direction of change |
| `confidence` | Reliability of the decision |
| `data_quality` | Reliability of input data |
| `stability` | Smoothness or persistence of the signal |
| `adjustment_intensity` | Recommended strength of allocation or rebalance action |
| `reason_codes` | Machine-readable decision reasons |
| `as_of_date` | Date the score is valid for |
| `parameter_version` | Parameter set used |
| `model_version` | Model or logic version used |

---

## 5.3 Score Normalization

Raw indicators must not be combined directly.

Examples:

| Raw Indicator | Possible Feature / Score |
|---|---|
| Interest rate | Z-score, percentile, rate-of-change |
| FX rate | 3-month change, long-term deviation |
| Export data | YoY growth, MoM trend, normalized surprise |
| Equity price | 3/6/12-month momentum |
| Volatility | historical percentile, realized vol trend |
| Valuation | relative historical band position |
| Earnings | revision trend, surprise score |
| Flows | volume, institutional/foreign net flow score |

---

## 5.4 Score Smoothing

Raw scores must pass through a smoothing layer before being used for decisions.

Required conceptual flow:

```text
raw_score
→ normalized_score
→ smoothed_score
→ confidence_adjusted_score
→ decision_score
```

Purpose:

- reduce noise;
- avoid sudden allocation changes;
- account for data release lag;
- improve decision stability;
- reduce overtrading.

---

# 6. Threshold Policy

## 6.1 Permitted Uses of Thresholds

Thresholds are allowed for:

- detecting missing data;
- detecting stale data;
- detecting anomalous data;
- enforcing account/legal constraints;
- order safety checks;
- minimum order size checks;
- score normalization boundaries;
- warning levels;
- emergency circuit breakers.

---

## 6.2 Prohibited Uses of Thresholds

Thresholds must not be used for:

- immediate macro regime switching;
- direct risk-on/risk-off switching;
- sudden equity/bond/cash allocation changes;
- direct buy/sell decisions;
- direct sector inclusion or exclusion;
- immediate target weight expansion;
- replacing composite score logic.

Thresholds may support interpretation, but they must not dominate the investment decision engine.

---

# 7. Hard Constraint Policy

## 7.1 Definition

A hard constraint is a rule that cannot be overridden by scores.

Even if an asset has a high attractiveness score, it must not be included if it violates a hard constraint.

---

## 7.2 Examples

Hard constraints include:

- product is not tradable in the selected account;
- IRP risky-asset limit violation;
- leveraged/inverse/futures product restrictions;
- insufficient cash;
- minimum order unit not satisfied;
- market suspension;
- product delisting or trading halt;
- missing account balance data;
- order validation failure;
- API state unknown;
- regulatory or broker-specific restriction.

---

## 7.3 Processing Order

```text
Score-Based Decision
→ Hard Constraint Filter
→ Risk Budget Filter
→ Execution Candidate
```

Hard constraints must not be softened into scores.

---

# 8. Data Principles

## 8.1 Data Layer Separation

Data must be separated into:

```text
raw_data
feature_data
score_data
decision_data
```

Raw data must be immutable where practical.

Derived data must be reproducible from raw data, feature definitions, and parameter versions.

---

## 8.2 Data Timing and Availability

Backtests and simulated decisions must use only data available at the simulated decision time.

Prohibited:

- using earnings before announcement;
- using finalized export/import data before release;
- using revised macro data as if available historically;
- using future ETF constituents;
- using survivorship-biased universes without handling;
- using future price data in current signal calculations.

---

## 8.3 Data Update Frequency

Different data categories have different update cycles.

| Data Type | Typical Frequency |
|---|---|
| Price | Daily or intraday |
| Volume | Daily |
| FX | Daily or intraday |
| Interest rates | Daily |
| VIX / MOVE | Daily |
| Export/import | Monthly |
| CPI / employment | Monthly |
| Company earnings | Quarterly |
| ETF constituents | Daily to monthly |
| Account balances | Daily or before order generation |

Do not treat monthly or quarterly data as real-time.

---

## 8.4 Data Quality Metadata

Important data sources should carry:

```json
{
  "source": "string",
  "as_of_date": "YYYY-MM-DD",
  "updated_at": "YYYY-MM-DDTHH:MM:SS",
  "quality_score": 0.0,
  "missing_ratio": 0.0,
  "is_stale": false
}
```

If data quality is poor, the system must choose one of:

```text
reduce_signal_weight
hold
review_required
use_conservative_fallback
risk_reduce_only
```

The system must not increase risk when data quality is poor.

---

# 9. Parameter Management

## 9.1 Parameters Are Data

Strategy parameters must not be hardcoded.

Examples of parameters that must be configurable:

- moving average periods;
- momentum lookback windows;
- score weights;
- volatility normalization windows;
- sector maximum weights;
- account-level risk limits;
- rebalancing bands;
- turnover limits;
- tax assumptions;
- transaction cost assumptions;
- hedge ratio policies;
- drawdown response rules.

---

## 9.2 Parameter Metadata

All strategy parameters should have:

```json
{
  "name": "string",
  "value": "any",
  "version": "string",
  "valid_from": "YYYY-MM-DD",
  "valid_to": null,
  "source": "string",
  "reason": "string",
  "backtest_result": "string or object",
  "walk_forward_result": "string or object",
  "approved": true
}
```

---

## 9.3 Parameter Change Control

Parameter changes must record:

- previous value;
- new value;
- reason;
- evidence;
- affected modules;
- backtest impact;
- walk-forward impact;
- expected live impact;
- rollback condition;
- approval status.

---

## 9.4 Missing Parameter Behavior

If a required parameter is missing, use a conservative state:

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

---

# 10. Macro Regime Engine

## 10.1 Regime as Distribution

The macro regime engine must output a distribution, not only a label.

Bad:

```json
{
  "regime": "risk_off"
}
```

Preferred:

```json
{
  "regime_distribution": {
    "risk_on_growth": 0.42,
    "neutral": 0.24,
    "inflation_pressure": 0.16,
    "recession_risk": 0.11,
    "volatility_stress": 0.07
  },
  "dominant_regime": "risk_on_growth",
  "confidence": 0.42
}
```

The dominant regime is descriptive.
Allocation must use the full distribution.

---

## 10.2 Macro Input Categories

Use multiple categories where available:

- interest rates;
- inflation;
- FX;
- liquidity;
- credit spreads;
- volatility;
- economic activity;
- export/import data;
- commodity prices;
- market trend;
- market breadth.

A single indicator must not determine the macro regime.

---

## 10.3 Regime Is Input, Not Conclusion

A high risk-on score does not automatically imply aggressive equity expansion.

Final allocation must also consider:

- sector score;
- valuation burden;
- volatility;
- risk budget;
- portfolio concentration;
- account constraints;
- transaction cost;
- tax impact;
- data quality;
- confidence.

---

# 11. Sector Scoring Engine

## 11.1 Decomposable Sector Scores

Sector scoring must be explainable.

Each sector should include applicable components:

- Macro Fit Score;
- Industry Momentum Score;
- Earnings Trend Score;
- Price Momentum Score;
- Valuation Score;
- Supply-Demand Score;
- Risk Penalty Score;
- Data Quality Score;
- Confidence Score.

---

## 11.2 Sector Universe Configuration

Sector definitions must not be hardcoded in strategy logic.

Example:

```yaml
sectors:
  semiconductor:
    enabled: true
    indicators:
      - export_yoy
      - sox_momentum
      - memory_price_trend
    asset_candidates: []

  robot:
    enabled: true
    indicators:
      - automation_capex
      - manufacturing_pmi
      - order_growth
    asset_candidates: []

  bio:
    enabled: true
    indicators:
      - rate_environment
      - clinical_event_score
      - earnings_revision
    asset_candidates: []
```

Adding a sector should normally require configuration updates, not code rewrites.

---

## 11.3 Sector Decision Behavior

Sector decisions must follow score flow.

| Score State | Preferred Behavior |
|---|---|
| score improving + confidence rising | gradual target increase candidate |
| score improving + volatility rising | limited increase or hold |
| score stable + overweight | stop new buys, hold |
| score falling + overweight | partial reduction candidate |
| score falling + risk pressure | reduction candidate |
| data quality poor | review required or hold |

---

# 12. Risk Budget Engine

## 12.1 Risk Budget Is Central

Asset weight must not be determined only by attractiveness score.

Allocation must consider:

- expected return score;
- volatility;
- correlation;
- drawdown contribution;
- account constraints;
- liquidity;
- tax;
- transaction cost;
- existing position weight;
- data quality;
- confidence.

---

## 12.2 Portfolio-Level and Account-Level Risk

The system must distinguish total portfolio risk and account-level risk.

| Account | Risk Management Focus |
|---|---|
| Taxable | growth exposure, satellite concentration, tax impact |
| ISA | tax efficiency, domestic-listed instruments, medium-term allocation |
| Pension | long-term growth, volatility control |
| IRP | risky-asset limit, product restrictions, defensive growth |

---

## 12.3 Risk as Penalty and Constraint

Most risks should reduce scores or reduce allocation intensity.

However, hard constraints must block the action.

Conceptual score:

```text
Final Asset Score
= Opportunity Score
- Volatility Penalty
- Concentration Penalty
- Liquidity Penalty
- Valuation Burden
- Data Quality Penalty
```

---

# 13. Allocation Engine

## 13.1 Target Weights Are Ranges

Assets and sectors should have target ranges, not fixed weights.

```json
{
  "asset": "robot_sector",
  "min_weight": 0.00,
  "base_weight": 0.05,
  "max_weight": 0.15,
  "current_target": 0.08
}
```

The `current_target` must be calculated from score flow and adjusted gradually.

---

## 13.2 Allocation Flow

```text
Base Weight
+ Macro Regime Adjustment
+ Sector Score Adjustment
+ Conviction Adjustment
- Risk Penalty Adjustment
- Concentration Penalty
- Cost Penalty
- Tax Penalty
→ Preliminary Target Weight
→ Hard Constraint Filter
→ Final Target Weight
```

---

## 13.3 Change Controls

Allocation changes must consider:

- maximum change per rebalance;
- monthly turnover limit;
- confidence adjustment;
- data quality adjustment;
- stability adjustment;
- transaction cost threshold;
- tax impact;
- account-specific constraints.

---

# 14. Satellite Sector Policy

## 14.1 Do Not Mechanically Sell Winners

A high-growth satellite sector must not be sold automatically because it rose above a previous target.

First evaluate:

- sector score stability;
- sector score improvement;
- fundamental support;
- industry momentum;
- valuation burden;
- volatility increase;
- portfolio risk contribution;
- account constraints;
- better alternatives.

---

## 14.2 Gradual Target Expansion

Satellite target expansion is allowed only when the score flow supports it.

Required positive evidence may include:

- improving Sector Total Score;
- improving Macro Fit Score;
- improving Industry Momentum Score;
- improving Earnings Trend Score;
- positive Price Momentum Score;
- available Risk Budget Score;
- sustainable Valuation Score;
- sufficient Data Quality Score;
- sufficient Confidence Score.

---

## 14.3 Satellite Action Matrix

| Condition | Action |
|---|---|
| overweight + score stable | stop new buys, hold |
| overweight + score improving | consider gradual target expansion |
| overweight + score falling | partial reduction candidate |
| overweight + risk limit pressure | reduction candidate |
| score improving + risk budget available | buy candidate |
| score improving + volatility spike | hold or limited buy |
| data quality poor | review required |

---

# 15. Rebalancing Engine

## 15.1 Purpose of Rebalancing

Rebalancing is not mechanical restoration to old weights.

Its purpose is to:

- maintain risk limits;
- prevent excessive concentration;
- preserve high-conviction positions;
- reduce low-conviction positions;
- allocate new cash efficiently;
- minimize unnecessary taxes and transaction costs;
- avoid account constraint violations.

---

## 15.2 Rebalancing Score

Conceptual structure:

```text
Rebalancing Score
= Weight Drift Score
+ Conviction Change Score
+ Risk Limit Pressure Score
+ Cash Availability Score
+ Cost Efficiency Score
+ Tax Efficiency Score
- Turnover Penalty
```

---

## 15.3 Rebalancing Intensity

Rebalancing should output intensity, not just action.

Possible semantics:

```text
0.0        → no action
low        → adjust with new cash
medium     → buy candidates
high       → rebalance candidates including partial sells
very high  → user review required
constraint → block or reduce
```

Numeric bands must be configurable.

---

# 16. Account Constraint Engine

## 16.1 Explicit Account Modeling

The system must explicitly distinguish account types:

- taxable account;
- ISA;
- pension account;
- IRP.

---

## 16.2 Account Role Configuration

Account roles must be configurable.

Example:

```yaml
accounts:
  taxable:
    role: aggressive_growth
    allow_satellite: true

  isa:
    role: tax_efficient_growth
    allow_satellite: true

  pension:
    role: long_term_growth
    allow_satellite: limited

  irp:
    role: defensive_growth
    allow_satellite: false
```

If the user explicitly defines an account role, that role takes priority.

---

## 16.3 Constraint Priority

Account constraints override investment attractiveness.

High score does not justify a prohibited action.

---

# 17. Backtest Engine

## 17.1 Backtest Requirement

No strategy logic may be promoted to production without backtesting.

Backtests are required for:

- regime score logic;
- sector score logic;
- risk budget logic;
- allocation logic;
- rebalancing logic;
- account constraint logic;
- order candidate logic.

---

## 17.2 Required Metrics

Backtests should report:

- CAGR;
- MDD;
- annualized volatility;
- Sharpe ratio;
- Sortino ratio;
- Calmar ratio;
- turnover;
- cost-adjusted return;
- tax-adjusted return;
- regime-by-regime performance;
- contribution analysis;
- stress-period performance;
- parameter sensitivity.

---

## 17.3 Required Validation

Use:

- in-sample validation;
- out-of-sample validation;
- walk-forward validation;
- transaction cost modeling;
- tax modeling where applicable;
- leakage prevention;
- survivorship-bias handling;
- stress testing.

---

## 17.4 Rejection Criteria

Reject or downgrade strategies that:

- rely on future data;
- work only in one regime;
- have extreme turnover;
- collapse after costs;
- collapse after taxes;
- are too sensitive to parameters;
- have unexplained performance;
- violate account constraints;
- increase drawdown without adequate return improvement.

---

# 18. Execution Engine

## 18.1 Decision and Execution Separation

The default workflow:

```text
1. Calculate target weights.
2. Calculate rebalancing intensity.
3. Generate order candidates.
4. Validate account and order constraints.
5. Request user review or approval.
6. Execute only if execution mode allows it.
7. Store execution and fill logs.
```

Automatic execution must not be the default.

---

## 18.2 Conditions for Automatic Execution

Automatic execution can be considered only after:

- backtest passed;
- walk-forward validation passed;
- order validation is implemented;
- account constraint validation is implemented;
- partial-fill handling is implemented;
- API error handling is implemented;
- execution logs are stored;
- user approval policy is defined;
- emergency stop is implemented.

---

# 19. Reporting and Audit

## 19.1 Required Questions

The system must be able to answer:

- Why was this asset bought?
- Why was this asset not sold?
- Why was this asset reduced?
- Why did this sector target weight increase?
- Why was rebalancing skipped?
- Which data was used?
- What was the data as-of date?
- Which parameter version was used?
- Which model version was used?
- Did the decision violate any account constraints?
- What were the transaction cost and tax implications?
- How did the strategy perform in weak backtest regimes?

---

## 19.2 Decision Log

Decision logs should include:

```json
{
  "date": "YYYY-MM-DD",
  "data_snapshot_id": "snapshot_id",
  "parameter_version": "parameter_version",
  "model_version": "model_version",
  "macro_scores": {},
  "sector_scores": {},
  "risk_budget_scores": {},
  "target_weights": {},
  "current_weights": {},
  "rebalance_scores": {},
  "account_constraints": {},
  "decision": "HOLD",
  "adjustment_intensity": 0.0,
  "reason_codes": [],
  "warnings": []
}
```

---

# 20. AI Coding Agent Rules

## 20.1 Before Editing Code

AI coding agents must:

1. inspect the current structure;
2. identify the minimal safe change;
3. preserve existing behavior unless change is explicitly required;
4. avoid broad refactoring unless requested;
5. add or update tests for strategy logic;
6. document non-trivial decisions;
7. avoid inventing missing business rules.

---

## 20.2 Clarification Required

Ask for clarification when:

- account type is unclear;
- investable universe is unclear;
- data source is unclear;
- execution mode is unclear;
- score formula is undefined;
- parameter default has no basis;
- backtest period is unclear;
- hard constraint boundary is unclear.

If implementation must proceed despite uncertainty, use conservative behavior:

```text
NO_ACTION
HOLD
REVIEW_REQUIRED
RISK_REDUCE_ONLY
```

---

## 20.3 Testing Required

Tests are required for:

- data cleaning;
- feature calculation;
- score calculation;
- regime distribution calculation;
- sector scoring;
- risk budget calculation;
- target allocation calculation;
- rebalancing score calculation;
- account constraint validation;
- order candidate generation;
- backtest simulation;
- future-data leakage prevention;
- parameter loading and versioning;
- conservative fallback behavior.

---

# 21. Prohibited Patterns

The following are prohibited:

1. Hardcoded strategy parameters.
2. Single-threshold regime switching.
3. Boolean-driven buy/sell logic.
4. Live strategy logic without backtesting.
5. Future-data leakage in backtests.
6. Ignoring account constraints.
7. Signals without data quality checks.
8. Unexplained buy/sell decisions.
9. Single-indicator risk-on/risk-off decisions.
10. Excessive single-sector concentration without risk budget handling.
11. Ignoring transaction costs or taxes.
12. Default automatic order execution.
13. Aggressive buying during data/API error states.
14. Selecting strategies by return only.
15. Overfit parameter usage.
16. Softening hard constraints into scores.
17. Changing target weights without score changes.
18. Large unverified refactors.
19. Mapping raw data directly to orders.
20. Mapping dominant regime directly to fixed weights.
21. Treating account role defaults as immutable.
22. Treating backtest performance as proof of future performance.

---

# 22. Development Priority

Development should proceed in this order:

| Phase | Goal |
|---:|---|
| 1 | Define asset universe |
| 2 | Define account constraint model |
| 3 | Build data pipeline |
| 4 | Build feature layer |
| 5 | Build score layer |
| 6 | Build backtest engine |
| 7 | Build macro regime engine |
| 8 | Build sector scoring engine |
| 9 | Build risk budget engine |
| 10 | Build allocation engine |
| 11 | Build rebalancing engine |
| 12 | Build reporting/audit layer |
| 13 | Generate order candidates |
| 14 | Add user-approved execution |
| 15 | Consider limited automatic execution |

Automatic execution comes last.

---

# 23. Final Quality Standard

A system change is acceptable only if it preserves these standards:

```text
1. All investment decisions are score-based.
2. Every score has traceable data and versions.
3. Allocation changes are gradual.
4. Rebalancing has intensity, not only action.
5. Order candidates pass hard constraints.
6. Strategy logic is backtestable.
7. Backtests prevent future-data leakage.
8. Parameters are versioned data.
9. Buy/sell/hold decisions are explainable.
10. Errors and uncertainty fall back conservatively.
```

---

# 24. Final Non-Negotiable Rules

```text
No Threshold Switch.
Score Flow is mandatory.
Hard Constraints override scores.
Backtest before execution.
Explain every decision.
Use conservative fallback on uncertainty or errors.
Do not hardcode strategy parameters.
Do not default to automatic execution.
```
