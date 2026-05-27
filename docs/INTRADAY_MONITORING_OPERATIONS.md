# Intraday Monitoring Operations

## How To Enable Or Disable Intraday Monitoring

Edit `config/intraday_monitoring.yaml`:

```yaml
intraday_monitoring:
  enabled: true
```

Set `enabled: false` to make collection return a no-op result.

## How To Run One Collection Pass Manually

Use the API endpoint:

```bash
curl -X POST "http://localhost:8000/api/intraday/collect/run-once?force=true"
```

Without `force=true`, the collector respects the configured regular session window.

## How To Inspect Latest Snapshots

```bash
curl "http://localhost:8000/api/intraday/snapshots/latest?market=KRX&limit=50"
```

Optional comma-separated symbols are supported:

```bash
curl "http://localhost:8000/api/intraday/snapshots/latest?symbols=005930,360750"
```

## How To Inspect Recent Events

```bash
curl "http://localhost:8000/api/intraday/events/recent?limit=50"
```

Filters include `event_type`, `event_level`, and `acknowledged`.

## How To Acknowledge Events

```bash
curl -X POST "http://localhost:8000/api/intraday/events/1/acknowledge"
```

Acknowledgement updates only the monitoring event state.

## Expected Market-session Behavior

The collector uses Asia/Seoul by default and includes the configured full regular session from `regular_session_start` through `regular_session_end`. Holiday handling is not implemented; unknown holiday state is treated conservatively as an operational concern, not a trading signal.

## Common Failure Modes

- Monitoring disabled: returns `status: no_op`.
- Outside regular session: returns `status: no_op` unless forced.
- Unsupported market/provider: symbol is excluded from the monitoring universe.
- Missing or non-positive price: snapshot is not stored and a warning is returned.
- Missing lookback data: no event is created and a warning is returned.
- Low quality or stale data: normal-confidence event detection is skipped or downgraded with warnings.

## Provider/API Error Handling

Provider failures are recorded per symbol as warnings. One failed symbol does not abort the full collection pass.

The current implementation uses read-only price paths. It does not require broker order permission and does not submit orders.

## DB Error Handling

Repository writes roll back on DB failure and surface a repository error. Alert processing handles repository errors conservatively by returning warnings without generating alert payloads.

## Test Command

Run the intraday suite:

```bash
.venv/bin/python -m pytest -q tests/test_intraday_config_universe.py tests/test_intraday_repository.py tests/test_intraday_collector.py tests/test_intraday_event_detector.py tests/test_intraday_alert_engine.py tests/test_intraday_api.py tests/test_intraday_strategy_isolation.py
```

Run the full non-live suite:

```bash
.venv/bin/python -m pytest -q
```
