# 2026-05-24 백테스트 시장 데이터 기반 엔진 구현

## 작업 범위

`docs/DevelopPlans/back_test.md`의 백테스트 개발 계획 중 실제 계좌 연동과 무관한 서버 핵심 흐름을 우선 적용했다. 이번 실행에서는 외부 API를 백테스트 실행 중 호출하지 않고, DB에 저장된 가격/환율 데이터만 사용해 결과를 재현하는 구조까지 구현했다.

## 개발 내용

### DB 스키마와 대표 자산 설정

- `asset_universe`, `market_prices`, `fx_rates`, `backtest_positions`, `backtest_trades` 테이블과 조회 인덱스를 추가했다.
- `config/backtest_assets.yaml`을 추가해 국내주식, 해외주식, 채권, ETF, 현금의 대표 백테스트 자산을 정의했다.
- `ensure_dashboard_tables()` 실행 시 대표 자산 설정을 `asset_universe`에 seed하도록 했다.

### 시장 데이터 서비스

- `api/market_data_service.py`를 추가했다.
- 자산 유니버스 조회, 자산군-자산코드 매핑, 가격/환율 matrix 조회, 가격/환율 커버리지 검증, look-ahead 없는 `on_or_before` 조회를 구현했다.
- `adj_close`가 있으면 우선 사용하고, 없으면 `close`를 사용한다.

### 실제 가격 기반 백테스트 엔진

- `api/strategy_allocator.py`에 `StaticTargetAllocator`를 추가했다.
- 기존 UI/API에서 쓰던 `DOMESTIC_STOCK`, `FOREIGN_STOCK`, `BOND`, `CASH` 별칭을 한국어 자산군 설정으로 매핑한다.
- `api/backtest_engine.py`를 추가했다.
- 초기자본 기준 가상 매수, 리밸런싱 날짜별 목표 비중 재조정, 일자별 평가, KRW 기준 USD 환산, drawdown, 총수익률, 연환산수익률, 변동성을 계산한다.
- 현금은 `CASH_KRW` manual 자산으로 처리하고 가격/환율은 1로 평가한다.

### 백테스트 API 교체

- `api/services.py`의 기존 가정수익률 기반 `_annual_return_for_asset()`, `_simulate_backtest_points()` 흐름을 제거했다.
- `POST /api/backtests/run`은 `BacktestEngine` 결과를 `backtest_runs`, `backtest_points`, `backtest_positions`, `backtest_trades`에 저장한다.
- `GET /api/backtests/runs`, `GET /api/backtests/runs/{id}` 응답에 포지션과 거래 내역을 포함하도록 확장했다.
- `web/lib/types.ts`의 백테스트 응답 타입에 positions/trades를 반영했다.

## 생성 커밋

- `6693641 feat: add backtest market data schema`
- `508c95a feat: add market data coverage service`
- `95bf6b3 feat: add price based backtest engine`
- `83740c0 feat: run backtests with market data engine`

## 검증

통과:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_market_data_schema.py
PYTHONPATH=. .venv/bin/python -m pytest tests/test_market_data_service.py
PYTHONPATH=. .venv/bin/python -m pytest tests/test_backtest_engine.py
PYTHONPATH=. .venv/bin/python -m pytest tests/test_api_backtests.py
```

묶음 검증:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_api_backtests.py tests/test_backtest_engine.py tests/test_market_data_service.py tests/test_market_data_schema.py
```

주의:

```bash
cd web
npm run lint
```

위 명령은 이번 백테스트 변경과 무관한 `web/components/dashboard/DailyCheckPanel.tsx`의 기존 `react-hooks/set-state-in-effect` 오류로 실패한다.

## 미작업 내용

- PR 3 데이터 수집기: Yahoo 등 외부 가격 데이터 수집 파이프라인과 `scripts/collect_historical_data.py`는 아직 구현하지 않았다.
- PR 6 시장 데이터 API: `/api/market-data/assets`, `/api/market-data/coverage`, `/api/market-data/collect`는 아직 없다.
- PR 7 프론트 연결: `/backtests` 화면에서 데이터 커버리지 확인, 수집 실행, 포지션/거래 상세 표시를 아직 연결하지 않았다.
- 동적 TripleA allocator: 현재는 `targets` 기반 static target allocator이며, 위험예산/매크로/리밸런싱 엔진을 과거 시점별로 재현하는 allocator 분리는 남아 있다.
- 거래비용: 수수료, 슬리피지, 세금은 저장 필드만 있고 계산값은 0이다.
- 백테스트 데이터 품질: 배당, 종목 생존편향, 최소 주문 단위, 휴장일 보정은 MVP 제외 또는 후속 과제다.
- 실제 계좌 연동: 이번 요청 범위에서 제외했다.

## 다음 실행 권장 순서

1. `tests/test_api_market_data.py`를 먼저 만들고 시장 데이터 조회/커버리지 API를 구현한다.
2. 외부 API 호출은 백테스트 실행 경로가 아니라 별도 collector/script에서만 수행한다.
3. 수집기가 저장한 `market_prices`, `fx_rates`를 기준으로 `/backtests` 화면에서 커버리지 상태를 보여준다.
4. 포지션/거래 상세 테이블은 이미 API 응답에 포함되므로 UI 표시만 추가하면 된다.
