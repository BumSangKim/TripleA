# Score Layer Specification

The Score Layer converts feature outputs into comparable, normalized, smoothed, confidence-adjusted, data-quality-aware, versioned scores.

## Purpose

The layer receives Feature Layer outputs such as raw feature values, feature snapshot IDs, plugin IDs, feature keys, confidence, and data quality metadata. It emits decision-ready score snapshots for downstream macro, sector, risk, allocation, and rebalancing engines.

## Contract

Each score output includes the score key, score type, subject type and ID, raw value, `normalized_score`, `smoothed_score`, `confidence_adjusted_score`, `decision_score`, previous score metadata, confidence, data quality, stability, smoothing metadata, reason codes, warnings, source plugin metadata, feature snapshot ID, parameter version, and model version.

Score values are bounded to `0.0 <= score <= 1.0`. Penalties are also represented as bounded positive values, not negative scores.

## Score Flow

```text
raw feature value
-> normalized_score
-> smoothed_score
-> confidence_adjusted_score
-> decision_score
```

## Score Definitions

Definitions are config driven. A score definition declares source plugin and feature keys, normalization method and params, direction, smoothing method, base/min/max spans, confidence and data-quality rules, enabled state, parameter version, and model version.

## Normalization And Direction

Supported methods include `min_max`, `bounded_linear`, `z_score`, `percentile`, `inverse_percentile`, and `neutral_band`. Supported direction values include `higher_is_better`, `higher_is_worse`, `lower_is_better`, `lower_is_worse`, and `neutral_band`. Unsupported methods fail safely with warnings and neutral/review-required output.

## EMA Smoothing

EMA smoothing uses:

```text
alpha = 2 / (span + 1)
ema_today = alpha * current_value + (1 - alpha) * previous_ema
```

If no previous score exists, the normalized score is the first smoothed score.

## Versioned Smoothing Parameter Override

The effective span is resolved as:

```text
base_span
-> event_profile span override
-> approved manual override
-> min_span / max_span clamp
-> effective_span
```

Event profiles and manual overrides are auditable. Manual overrides carry `valid_from`, `valid_to`, approval state, reason, and metadata. Unknown, unapproved, or expired overrides fall back to base/event profile behavior. Every output stores `effective_span`, whether an override was applied, the reason, the event profile, and expiry metadata.

Risk-reduction and stress-detection scores may become more responsive during stress. Risk-increase, buy-intensity, and opportunity scores must not become more aggressive by default during uncertainty, including `black_swan_watch`.

## Confidence And Data Quality

Confidence adjustment pulls scores toward neutral:

```text
confidence_adjusted_score = neutral + (smoothed_score - neutral) * confidence
```

Data quality adjustment pulls the confidence-adjusted score toward neutral and emits warnings when data quality is below minimum. Low confidence or low data quality must not increase risk. Missing feature data returns review-required warnings rather than buy/increase-risk behavior.

## Persistence

Score runs and score values persist run IDs, as-of dates, feature snapshot IDs, event profiles, source plugin and feature metadata, parameter/model versions, warnings, reason codes, and the exact `effective_span` used.

## Conservative Fallback

Missing required data, unknown methods, invalid spans, poor quality, stale feature data, and unsupported event profiles must produce explicit warnings and conservative outputs such as neutral score, `REVIEW_REQUIRED`, `HOLD`, `NO_ACTION`, or risk-reduce-only behavior downstream.

## Out Of Scope

The Score Layer must not:

- generate buy/sell orders;
- generate target weights;
- decide final macro regimes;
- decide final sector allocation;
- execute trades;
- bypass account constraints.

## Testing Requirements

Tests must cover score contracts, config loading, normalization, directionality, EMA smoothing, event/manual span overrides, expired overrides, confidence and data-quality adjustment, persistence, runner reproducibility, missing data fallback, and proof that the layer does not generate orders, mutate allocation targets, or call broker APIs.
