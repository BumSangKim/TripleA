# Market Data DB Integration Spec

## 1. Purpose

Phase Pre-3 adds a read-only market price query contract and verifies that quote data can be written to and read from a test DB. The feature is data plumbing only; it does not create live execution behavior.

## 2. Read-Only Price Provider Contract

`api/market_data/price_provider.py` defines `PriceProvider.get_current_price()` and a `PriceQuote` model. The default provider is a mock provider for normal tests. A KIS read-only adapter may be selected for explicit live smoke tests and only calls quote endpoints.

## 3. Quote Freshness Policy

The quote contract accepts current price, latest displayed price, prior close, or the most recent provider quote. Smoke tests validate query capability and `price > 0`; they do not require the quote timestamp or trade date to equal today.

## 4. Live Price Smoke Test

Run the live price smoke test explicitly:

```bash
RUN_LIVE_PRICE_SMOKE=1 .venv/bin/python -m pytest tests/integration/test_live_price_query_smoke.py -q
```

Without `RUN_LIVE_PRICE_SMOKE=1`, the test is skipped.

## 5. Market Data DB Fields

`api/market_data/repository.py` creates a `price_quotes` table with:

```text
id, asset_id, symbol, market, price, currency, provider, as_of, trade_date, raw_json, created_at
```

Price is stored as text and restored as `Decimal` to avoid unnecessary precision loss.

## 6. Mock Quote DB Write/Read Test

`tests/test_market_data_db_write_read.py` resolves the initial ETF candidate universe, creates a mock quote, stores it in a temporary SQLite DB, and verifies the latest record can be read back without network or API credentials.

## 7. Live Data To DB E2E Test

Run the explicit e2e test with both gates:

```bash
RUN_LIVE_PRICE_SMOKE=1 RUN_DB_INTEGRATION=1 .venv/bin/python -m pytest tests/integration/test_universe_live_data_db_e2e.py -q
```

The test resolves `initial_order_candidate_universe`, queries a limited number of ETF quotes, writes them to a temporary DB, and reads them back.

## 8. External API Test Skip Policy

Live API tests are skipped by default. They require explicit environment variables and available provider credentials. Default `pytest` remains offline-safe.

## 9. Separation From Sensitive Broker Functions

The Pre-3 market data path is separate from 주문, 잔고, 매수가능금액, and 계좌비밀번호 workflows. It must not submit broker orders, generate real orders, or require account password/order permission.

## 10. Phase 3 Connection Point

Phase 3 can build the data pipeline on top of the normalized `asset_master`, selector snapshots, read-only provider contract, and DB quote repository. Any execution-adjacent integration still requires a separate approved task.
