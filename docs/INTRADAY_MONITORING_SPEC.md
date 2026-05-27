# Intraday Monitoring Spec

## Purpose

Intraday monitoring records read-only intraday price snapshots, detects surge/drop/volume events, stores alert-ready rows, and exposes them through the API for display and review.

## Confirmed Requirements

- Monitor the enabled investable universe from `config/universe/asset_master.yml`.
- Use read-only provider paths only.
- Persist snapshots, events, and alert-ready records.
- Suppress duplicate alerts within the configured window.
- Keep events display/alert-only in this phase.

## Architecture Overview

- Config: `config/intraday_monitoring.yaml`
- Universe: `api/intraday/universe.py`
- Provider adapter and collector: `api/intraday/provider.py`, `api/intraday/collector.py`
- Repository and models: `api/intraday/models.py`, `api/intraday/repository.py`
- Detection and alert processing: `api/intraday/detector.py`, `api/intraday/alert.py`
- API router: `api/intraday/router.py`, registered in `api/main.py`

## Data Flow

1. Resolve monitoring symbols from the asset master.
2. Fetch read-only intraday/current price data.
3. Normalize provider payloads into `IntradayPriceSnapshot`.
4. Persist snapshots to `intraday_price_snapshot`.
5. Compare current snapshots to configured lookback windows.
6. Persist detected events and internal alert-ready rows.
7. Serve snapshots and events through `/api/intraday/*`.

## Config Structure

`config/intraday_monitoring.yaml` contains the enabled flag, collection interval, session times, provider name, lookback windows, price/volume alert thresholds, duplicate suppression window, stale-data tolerance, provider batch size, and dry-run flag.

Thresholds are monitoring-alert defaults only. They are not strategy parameters.

## Universe Resolution

The default resolver uses the asset master directly and includes supported KRX symbols unless they are explicitly disabled, missing a symbol/market, or unsupported by the current provider. Optional selector narrowing is available through `universe_selector`, but it is not required for default monitoring.

## DB Schema Summary

- `intraday_price_snapshot`: normalized snapshot rows with symbol, market, timestamp, price fields, volume fields, quality fields, stale flag, and raw payload.
- `intraday_event`: detected monitoring events with event type, level, lookback, base/current price, change rate, volume ratio, reason code, message, and acknowledgement state.
- `intraday_alert`: internal alert-ready records with channel, dedupe key, status, and sent timestamp.

## Snapshot Repository Behavior

Snapshots are upserted by `(symbol, market, captured_at)`. Non-positive prices and invalid quality scores are rejected. DB failures are rolled back and surfaced to callers as repository errors.

## Surge/Drop Detection Rules

For each configured lookback window, the detector finds the latest base snapshot at or before the target lookback time and computes:

```text
(current_price - base_price) / base_price * 100
```

Positive moves are compared against surge thresholds. Negative moves are compared against drop thresholds. Levels are `WATCH`, `WARNING`, and `CRITICAL`.

## Volume Spike Detection Rules

If current and base volumes are present and base volume is positive, the detector computes `current_volume / base_volume`. It creates `VOLUME_SPIKE` events when configured volume thresholds are crossed.

If a price event and volume event occur for the same window, the detector also creates `SURGE_WITH_VOLUME` or `DROP_WITH_VOLUME`.

## Alert And Deduplication Behavior

Alert dedupe keys use:

```text
{symbol}:{event_type}:{event_level}:{lookback_minutes}
```

The event level is part of the key, so escalation from `WATCH` to `WARNING` or `CRITICAL` is alert-worthy. Repeated alerts are allowed after `duplicate_suppression_minutes`.

## API Endpoints

- `GET /api/intraday/snapshots/latest`
- `GET /api/intraday/snapshots/{symbol}`
- `GET /api/intraday/events/recent`
- `GET /api/intraday/events/{symbol}`
- `POST /api/intraday/events/{event_id}/acknowledge`
- `POST /api/intraday/collect/run-once`

`run-once` performs one collection pass only. It does not start a scheduler or daemon.

## Strategy Isolation Boundary

Intraday data does not feed macro regime scores, sector scores, risk budgets, allocation, rebalancing, order candidates, broker submission, or execution. Tests in `tests/test_intraday_strategy_isolation.py` cover these boundaries.

## Future Extension Points

Future approved phases may integrate intraday data into score layers, risk monitoring, rebalancing intensity, order candidate hold/review rules, backtesting, dashboard notifications, or user-approved execution guardrails.

## Non-goals

- No live order execution.
- No broker order submission.
- No automatic trading.
- No strategy score changes.
- No allocation/rebalancing/order candidate integration.
- No always-running scheduler.
