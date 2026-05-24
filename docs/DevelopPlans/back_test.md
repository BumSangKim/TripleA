# 현재 TripleA 상태 기준 백테스트 개발 가이드라인

## 0. 내가 이해한 목표

원하는 기능은 단순히 “과거 수익률 차트”를 보는 기능이 아닙니다.

정확한 목표는 다음입니다.

```text
초기 자본을 입력한다.
과거 N년치 실제 가격/환율/필요 지표 데이터를 준비한다.
백테스트 기간의 각 리밸런싱 시점마다 TripleA의 자산 분배 알고리즘을 실행한다.
그 시점의 알고리즘 결과대로 가상 매수/매도한다.
실제 과거 가격으로 매일 또는 리밸런싱 주기마다 포트폴리오 가치를 평가한다.
최종 자산가치, 총수익률, 연환산수익률, MDD, 변동성, 거래내역을 확인한다.
```

---

# 1. 현재 코드 상태 요약

현재 TripleA에는 백테스트 기능의 **외형**은 이미 있습니다.

## 이미 있는 것

| 영역      | 현재 상태                                                                                   |
| ------- | --------------------------------------------------------------------------------------- |
| 백엔드 API | `POST /api/backtests/run`, `GET /api/backtests/runs`, `GET /api/backtests/runs/{id}` 존재 |
| DB      | `backtest_runs`, `backtest_points` 존재                                                   |
| 프론트     | `/backtests` 화면 존재                                                                      |
| 테스트     | `tests/test_api_backtests.py` 존재                                                        |
| 모드 정책   | `backtest` 모드는 결과 저장 가능, 주문 차단                                                          |
| 목표 비중   | `targets` 테이블에 기본 자산배분 목표 존재                                                            |
| 리밸런싱    | `get_target_deviations()`, `record_rebalance_results()` 존재                              |
| 위험예산    | `engine_allocations`, `get_risk_budget_items()` 존재                                      |

## 부족한 것

| 부족한 부분                | 설명                                            |
| --------------------- | --------------------------------------------- |
| 실제 과거 가격 데이터 없음       | `market_prices` 같은 가격 시계열 테이블이 없음             |
| 환율 데이터 없음             | 해외자산을 KRW로 환산할 수 없음                           |
| 데이터 수집기 없음            | 레거시 수집 파이프라인은 제거된 상태                          |
| 백테스트 엔진 없음            | 현재 `run_backtest()`는 실제 가격이 아니라 자산군별 가정수익률 사용 |
| 알고리즘 재현 구조 없음         | 현재 리밸런싱 로직은 “현재 DB 보유자산” 기준이라 과거 시점 재현이 어려움   |
| 포지션/거래 저장 없음          | 백테스트 결과의 매수·매도 내역을 검증하기 어려움                   |
| look-ahead bias 방지 없음 | 과거 특정 시점에서 미래 데이터를 차단하는 구조가 아직 없음             |

---

# 2. 가장 중요한 설계 원칙

## 핵심 원칙

```text
백테스트 실행 시점에는 외부 API를 호출하지 않는다.
```

구조는 반드시 이렇게 가야 합니다.

```text
데이터 수집기
  ↓
market_prices / fx_rates DB 저장
  ↓
백테스트 실행
  ↓
DB에 저장된 과거 데이터만 사용
  ↓
결과 저장
```

반대로 아래 방식은 피해야 합니다.

```text
백테스트 실행 중
  ↓
yfinance / KIS / 외부 API 호출
  ↓
받은 가격으로 바로 계산
```

이렇게 하면 재현성, 테스트 안정성, 속도, 장애 대응이 모두 나빠집니다.

---

# 3. 현재 구조에서 목표 구조로 바꾸는 방향

## 현재 구조

```text
api/services.py

run_backtest()
  → _normalize_backtest_targets()
  → _annual_return_for_asset()
  → _simulate_backtest_points()
  → backtest_runs 저장
  → backtest_points 저장
```

현재 백테스트는 실제 투자 시뮬레이션이 아닙니다.
자산군별 연간 가정수익률을 섞고, 임의의 충격값을 넣어 자산곡선을 만드는 구조입니다.

---

## 목표 구조

```text
run_backtest()
  → 요청 검증
  → 백테스트 대상 자산 매핑
  → 시장 데이터 커버리지 검증
  → BacktestEngine 실행
      → 각 리밸런싱 날짜마다 StrategyAllocator 실행
      → 목표 비중 산출
      → 가상 매수/매도
      → 일별 평가
      → drawdown 계산
  → backtest_runs 저장
  → backtest_points 저장
  → backtest_positions 저장
  → backtest_trades 저장
```

---

# 4. 개발 순서

## Phase 1. 백테스트 데이터 스키마 추가

먼저 `api/db.py`에 시장 데이터 테이블을 추가해야 합니다.

### 1-1. 자산 유니버스 테이블

```sql
CREATE TABLE IF NOT EXISTS asset_universe (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_code TEXT NOT NULL UNIQUE,
    symbol TEXT NOT NULL,
    name TEXT,
    asset_class TEXT NOT NULL,
    market TEXT,
    currency TEXT NOT NULL DEFAULT 'KRW',
    source_type TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);
```

예시:

| asset_code | symbol   | asset_class    | currency | source_type |
| ---------- | -------- | -------------- | -------- | ----------- |
| KOSPI      | ^KS11    | DOMESTIC_STOCK | KRW      | yahoo       |
| SPY        | SPY      | FOREIGN_STOCK  | USD      | yahoo       |
| QQQ        | QQQ      | GROWTH         | USD      | yahoo       |
| TLT        | TLT      | BOND           | USD      | yahoo       |
| CASH_KRW   | CASH_KRW | CASH           | KRW      | manual      |

---

### 1-2. 가격 테이블

```sql
CREATE TABLE IF NOT EXISTS market_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_code TEXT NOT NULL,
    price_date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL NOT NULL,
    adj_close REAL,
    volume REAL,
    currency TEXT NOT NULL,
    source TEXT NOT NULL,
    fetched_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(asset_code, price_date)
);

CREATE INDEX IF NOT EXISTS idx_market_prices_asset_date
ON market_prices(asset_code, price_date);
```

백테스트 계산 시 가격 기준은 다음으로 고정합니다.

```text
사용 가격 = adj_close가 있으면 adj_close, 없으면 close
```

---

### 1-3. 환율 테이블

```sql
CREATE TABLE IF NOT EXISTS fx_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    base_currency TEXT NOT NULL,
    quote_currency TEXT NOT NULL,
    rate_date TEXT NOT NULL,
    rate REAL NOT NULL,
    source TEXT NOT NULL,
    fetched_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(base_currency, quote_currency, rate_date)
);

CREATE INDEX IF NOT EXISTS idx_fx_rates_pair_date
ON fx_rates(base_currency, quote_currency, rate_date);
```

미국 ETF를 원화 기준으로 평가하려면 필수입니다.

```text
KRW 평가금액 = USD 가격 × 수량 × USD/KRW 환율
```

---

### 1-4. 백테스트 포지션 테이블

```sql
CREATE TABLE IF NOT EXISTS backtest_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES backtest_runs(id),
    point_date TEXT NOT NULL,
    asset_code TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    fx_rate REAL DEFAULT 1,
    market_value REAL NOT NULL,
    weight REAL NOT NULL,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_backtest_positions_run_date
ON backtest_positions(run_id, point_date);
```

---

### 1-5. 백테스트 거래 테이블

```sql
CREATE TABLE IF NOT EXISTS backtest_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES backtest_runs(id),
    trade_date TEXT NOT NULL,
    asset_code TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    fx_rate REAL DEFAULT 1,
    gross_amount REAL NOT NULL,
    fee REAL DEFAULT 0,
    slippage REAL DEFAULT 0,
    tax REAL DEFAULT 0,
    net_amount REAL NOT NULL,
    reason TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_backtest_trades_run_date
ON backtest_trades(run_id, trade_date);
```

---

## Phase 2. 자산 매핑 설정 추가

현재 `targets`는 `국내주식`, `해외주식`, `채권`, `ETF`, `현금` 같은 자산군 중심입니다.
백테스트는 실제 가격이 필요하므로 자산군을 실제 백테스트 자산으로 매핑해야 합니다.

새 파일을 추가합니다.

```text
config/backtest_assets.yaml
```

예시:

```yaml
base_currency: KRW

default_assets:
  국내주식:
    asset_code: KOSPI
    symbol: "^KS11"
    name: "KOSPI Index"
    asset_class: "국내주식"
    currency: KRW
    source_type: yahoo

  해외주식:
    asset_code: SPY
    symbol: "SPY"
    name: "SPDR S&P 500 ETF"
    asset_class: "해외주식"
    currency: USD
    source_type: yahoo

  채권:
    asset_code: TLT
    symbol: "TLT"
    name: "iShares 20+ Year Treasury Bond ETF"
    asset_class: "채권"
    currency: USD
    source_type: yahoo

  ETF:
    asset_code: QQQ
    symbol: "QQQ"
    name: "Invesco QQQ ETF"
    asset_class: "ETF"
    currency: USD
    source_type: yahoo

  현금:
    asset_code: CASH_KRW
    symbol: "CASH_KRW"
    name: "KRW Cash"
    asset_class: "현금"
    currency: KRW
    source_type: manual
```

개발 초기에는 대표 ETF/지수 1개로 단순화하는 게 맞습니다.
나중에 `assetCode`를 사용자가 직접 선택하도록 확장하면 됩니다.

---

## Phase 3. 과거 데이터 수집기 추가

추가할 디렉터리:

```text
api/data_collectors/
scripts/collect_historical_data.py
```

권장 구조:

```text
api/data_collectors/
├── __init__.py
├── base.py
├── yahoo_provider.py
├── manual_provider.py
├── fx_provider.py
└── collector.py
```

### 수집기 인터페이스

```python
# api/data_collectors/base.py

from dataclasses import dataclass
from datetime import date
from abc import ABC, abstractmethod

@dataclass
class PriceBar:
    asset_code: str
    price_date: date
    open: float | None
    high: float | None
    low: float | None
    close: float
    adj_close: float | None
    volume: float | None
    currency: str
    source: str


class HistoricalDataProvider(ABC):
    @abstractmethod
    def fetch_prices(
        self,
        asset_code: str,
        symbol: str,
        start_date: date,
        end_date: date,
        currency: str,
    ) -> list[PriceBar]:
        ...
```

---

### 수집 스크립트

```python
# scripts/collect_historical_data.py

from datetime import date
from dateutil.relativedelta import relativedelta

from api.db import ensure_dashboard_tables, get_conn
from api.data_collectors.collector import collect_backtest_data


def main():
    ensure_dashboard_tables()

    end_date = date.today()
    start_date = end_date - relativedelta(years=3)

    with get_conn() as conn:
        result = collect_backtest_data(
            conn=conn,
            start_date=start_date,
            end_date=end_date,
            asset_config_path="config/backtest_assets.yaml",
        )

    print(result)


if __name__ == "__main__":
    main()
```

실행:

```bash
PYTHONPATH=. python scripts/collect_historical_data.py
```

---

## Phase 4. 현재 자산분배 알고리즘을 백테스트 가능하게 분리

여기가 가장 중요합니다.

현재 `get_target_deviations()`는 백테스트 엔진에서 그대로 쓰면 안 됩니다.

이유는 다음입니다.

| 문제                      | 설명                                        |
| ----------------------- | ----------------------------------------- |
| 현재 날짜 의존                | 내부에서 `date.today()` 사용                    |
| 현재 DB 의존                | 현재 `holdings`, `account_snapshots`를 직접 조회 |
| 과거 시점 재현 불가             | `as_of_date` 개념이 없음                       |
| 미래 데이터 차단 불가            | 백테스트 시점별 데이터 제한 구조가 없음                    |
| 실행 결과가 포트폴리오 상태와 강하게 결합 | 순수한 자산배분 함수가 아님                           |

따라서 백테스트에 사용할 수 있는 순수 알고리즘 인터페이스를 새로 만들어야 합니다.

---

## 4-1. `StrategyAllocator` 추가

```text
api/strategy_allocator.py
```

```python
from dataclasses import dataclass
from datetime import date


@dataclass
class PortfolioState:
    cash: float
    positions: dict[str, float]       # asset_code -> quantity
    total_value: float


@dataclass
class MarketContext:
    as_of_date: date
    prices: dict[str, float]          # asset_code -> KRW converted price
    trailing_returns: dict[str, float]
    volatility: dict[str, float]
    macro: dict[str, float] | None = None


class StrategyAllocator:
    def allocate(
        self,
        *,
        as_of_date: date,
        portfolio: PortfolioState,
        market: MarketContext,
    ) -> dict[str, float]:
        """
        return:
            asset_code -> target weight
            예: {"KOSPI": 0.25, "SPY": 0.35, "TLT": 0.15, "QQQ": 0.10, "CASH_KRW": 0.15}
        """
        raise NotImplementedError
```

---

## 4-2. 첫 구현은 `StaticTargetAllocator`

처음부터 복잡한 동적 알고리즘을 넣지 말고, 현재 `targets`의 목표 비중을 실제 자산 코드로 변환하는 allocator부터 만듭니다.

```python
class StaticTargetAllocator(StrategyAllocator):
    def __init__(self, target_weights: dict[str, float]):
        self.target_weights = target_weights

    def allocate(self, *, as_of_date, portfolio, market) -> dict[str, float]:
        return self.target_weights
```

이 단계의 의미는 다음입니다.

```text
현재 TripleA 목표 비중대로 과거 3년 동안 투자했다면 어땠는가?
```

이게 1차 MVP입니다.

---

## 4-3. 이후 `TripleAAllocator`로 확장

그다음에 현재 구현된 리밸런싱·위험예산 로직을 순수 함수로 분리해 `TripleAAllocator`에 넣습니다.

```python
class TripleAAllocator(StrategyAllocator):
    def allocate(self, *, as_of_date, portfolio, market) -> dict[str, float]:
        # 1. 기본 목표 비중 로드
        # 2. 위험예산 확인
        # 3. 시장 변동성/추세/현금비중 조정
        # 4. 최종 목표 비중 반환
        return target_weights
```

주의할 점:

```text
TripleAAllocator 내부에서는 date.today() 사용 금지
현재 holdings 직접 조회 금지
현재 account_snapshots 직접 조회 금지
외부 API 호출 금지
as_of_date 이전 데이터만 사용
```

---

# 5. BacktestEngine 추가

새 파일:

```text
api/backtest_engine.py
```

## 핵심 역할

```text
BacktestEngine은 투자 알고리즘을 직접 판단하지 않는다.
BacktestEngine은 allocator가 준 목표비중대로 매매·평가만 한다.
```

즉 역할을 분리합니다.

```text
StrategyAllocator
  → 목표 비중 계산

BacktestEngine
  → 가격 조회
  → 주문 시뮬레이션
  → 포지션 갱신
  → 포트폴리오 평가
  → 성과지표 계산
```

---

## 엔진 설정 모델

```python
from dataclasses import dataclass
from datetime import date

@dataclass
class BacktestConfig:
    start_date: date
    end_date: date
    initial_capital: float
    rebalance_frequency: str
    base_currency: str = "KRW"
    fee_bps: float = 5.0
    slippage_bps: float = 5.0
    tax_bps: float = 0.0
```

---

## 백테스트 알고리즘

```text
1. start_date부터 end_date까지 거래일 캘린더를 만든다.
2. 각 자산의 가격 시계열을 DB에서 조회한다.
3. USD 자산은 USD/KRW 환율로 KRW 가격으로 변환한다.
4. 시작일에 allocator.allocate() 실행.
5. 목표 비중대로 초기 매수한다.
6. 매 거래일마다:
   - 자산별 평가금액 계산
   - 총 포트폴리오 가치 계산
   - drawdown 계산
7. 리밸런싱 날짜마다:
   - as_of_date 이전 데이터만 MarketContext에 전달
   - allocator.allocate() 실행
   - 현재 비중과 목표 비중 차이 계산
   - 매수/매도 주문 시뮬레이션
   - 수수료/슬리피지 차감
   - 포지션 수량 갱신
8. 종료일에 성과지표 계산.
9. points, positions, trades 반환.
```

---

# 6. `run_backtest()` 교체 방식

기존 `api/services.py`의 `run_backtest()`는 유지하되 내부 구현을 교체합니다.
API 경로를 바꾸지 않는 게 좋습니다.

## 현재

```python
annual_assumption = sum(
    weight * _annual_return_for_asset(asset)
    for asset, weight in weights.items()
)

values, drawdowns, period_returns, period_days = _simulate_backtest_points(...)
```

이 부분을 제거해야 합니다.

---

## 목표

```python
def run_backtest(conn, request):
    start = _parse_backtest_date(request.startDate, "startDate")
    end = _parse_backtest_date(request.endDate, "endDate")

    asset_weights = resolve_backtest_asset_weights(
        conn=conn,
        targets=request.targets,
    )

    validate_market_data_coverage(
        conn=conn,
        asset_codes=list(asset_weights.keys()),
        start_date=start,
        end_date=end,
        base_currency="KRW",
    )

    allocator = StaticTargetAllocator(asset_weights)

    result = BacktestEngine(conn).run(
        config=BacktestConfig(
            start_date=start,
            end_date=end,
            initial_capital=request.initialCapital,
            rebalance_frequency=request.rebalanceFrequency,
            fee_bps=request.feeBps,
            slippage_bps=request.slippageBps,
        ),
        allocator=allocator,
    )

    run_id = save_backtest_result(conn, request, result)

    return get_backtest_run(conn, run_id)
```

---

# 7. API 모델 확장

현재 `BacktestRunRequest`는 최소 입력만 받습니다.

```python
class BacktestRunRequest(BaseModel):
    name: str = "Backtest"
    startDate: str
    endDate: str
    initialCapital: float
    rebalanceFrequency: str = "monthly"
    targets: List[BacktestTarget] = Field(default_factory=list)
```

다음 필드를 추가하는 것이 좋습니다.

```python
class BacktestTarget(BaseModel):
    assetClass: str
    targetRatio: float
    assetCode: Optional[str] = None


class BacktestRunRequest(BaseModel):
    name: str = "Backtest"
    startDate: str
    endDate: str
    initialCapital: float
    rebalanceFrequency: str = "monthly"
    targets: List[BacktestTarget] = Field(default_factory=list)

    strategyMode: str = "static_target"   # static_target | triplea
    baseCurrency: str = "KRW"
    feeBps: float = 5.0
    slippageBps: float = 5.0
    taxBps: float = 0.0
```

## 전략 모드 구분

| strategyMode    | 의미                             |
| --------------- | ------------------------------ |
| `static_target` | 입력한 목표 비중을 고정 또는 주기적 리밸런싱      |
| `triplea`       | TripleA 자산 분배 알고리즘을 과거 시점마다 실행 |
| `benchmark`     | 벤치마크 단일 자산 비교용                 |

초기에는 `static_target`만 완성하고, 그다음 `triplea`를 붙이는 순서가 안전합니다.

---

# 8. 시장 데이터 API 추가

프론트에서 데이터가 있는지 확인할 수 있어야 합니다.

## 추가 API

```text
GET  /api/market-data/assets
GET  /api/market-data/coverage
POST /api/market-data/collect
```

---

## `GET /api/market-data/coverage`

예시 응답:

```json
{
  "ok": true,
  "startDate": "2023-05-24",
  "endDate": "2026-05-24",
  "assets": [
    {
      "assetCode": "SPY",
      "name": "SPDR S&P 500 ETF",
      "currency": "USD",
      "rows": 753,
      "firstDate": "2023-05-24",
      "lastDate": "2026-05-22",
      "status": "OK"
    },
    {
      "assetCode": "TLT",
      "name": "iShares 20+ Year Treasury Bond ETF",
      "currency": "USD",
      "rows": 700,
      "firstDate": "2023-08-01",
      "lastDate": "2026-05-22",
      "status": "INSUFFICIENT"
    }
  ]
}
```

---

## `POST /api/market-data/collect`

예시 요청:

```json
{
  "years": 3,
  "assetCodes": ["KOSPI", "SPY", "QQQ", "TLT", "CASH_KRW"]
}
```

---

# 9. 프론트엔드 변경 가이드

현재 `/backtests` 화면에는 조건 입력, 목표 비중 입력, 실행, 결과 표시가 있습니다.
여기에 아래를 추가합니다.

## 추가할 UI

| UI            | 설명                                 |
| ------------- | ---------------------------------- |
| 데이터 커버리지 카드   | 자산별 가격 데이터 보유 기간 표시                |
| 3년치 데이터 수집 버튼 | `POST /api/market-data/collect` 호출 |
| 전략 모드 선택      | `static_target`, `triplea` 선택      |
| 비용 입력         | fee bps, slippage bps              |
| 자산 매핑 표시      | `해외주식 → SPY`, `채권 → TLT`           |
| 데이터 부족 경고     | 수집 전에는 실행 버튼 비활성화                  |
| 거래내역 탭        | 리밸런싱 때 어떤 자산을 매수/매도했는지 표시          |
| 포지션 탭         | 날짜별 보유수량과 평가금액 표시                  |

---

## 권장 UI 흐름

```text
/backtests 진입
  ↓
GET /api/market-data/coverage
  ↓
데이터 부족 여부 표시
  ↓
부족하면 “3년치 데이터 수집” 버튼 표시
  ↓
수집 완료 후 coverage 재조회
  ↓
백테스트 실행 가능
  ↓
POST /api/backtests/run
  ↓
자산곡선 / drawdown / 수익률 / 거래내역 표시
```

---

# 10. 테스트 전략

## 10-1. 스키마 테스트

```text
tests/test_market_data_schema.py
```

검증 항목:

```text
asset_universe 생성됨
market_prices 생성됨
fx_rates 생성됨
backtest_positions 생성됨
backtest_trades 생성됨
market_prices UNIQUE(asset_code, price_date) 동작
```

---

## 10-2. 데이터 수집 테스트

```text
tests/test_market_data_collection.py
```

외부 API를 직접 호출하지 말고 fake provider를 사용합니다.

검증 항목:

```text
3년치 기간 계산
가격 데이터 upsert
재수집 시 중복 row 증가 없음
일부 자산 실패 시 status가 FAILED 또는 PARTIAL_SUCCESS
```

---

## 10-3. 엔진 테스트

```text
tests/test_backtest_engine.py
```

필수 케이스:

| 테스트            | 기대 결과           |
| -------------- | --------------- |
| 가격이 계속 상승      | 최종 평가금액 증가      |
| 가격이 하락         | drawdown 발생     |
| 월간 리밸런싱        | 월 경계에서 trade 발생 |
| 수수료 있음         | 수수료 없는 결과보다 낮음  |
| USD 자산 + 환율 상승 | KRW 평가금액 증가     |
| 데이터 부족         | 백테스트 실행 거부      |

---

## 10-4. API 테스트

기존 `tests/test_api_backtests.py`를 유지하면서 새 케이스를 추가합니다.

검증 항목:

```text
market_prices seed 삽입
POST /api/backtests/run 호출
backtest_runs 저장
backtest_points 저장
backtest_positions 저장
backtest_trades 저장
최종 수익률이 seed 데이터 기준 예상값과 일치
```

---

# 11. 구현 우선순위

## PR 1. DB 스키마와 자산 설정

목표:

```text
백테스트에 필요한 데이터 저장 기반을 만든다.
```

작업 파일:

```text
api/db.py
config/backtest_assets.yaml
tests/test_market_data_schema.py
```

완료 기준:

```bash
PYTHONPATH=. python -m pytest tests/test_market_data_schema.py
PYTHONPATH=. python -m pytest tests/test_api_backtests.py
```

---

## PR 2. 시장 데이터 서비스

목표:

```text
가격 데이터와 환율 데이터를 조회/검증하는 서비스 계층을 만든다.
```

작업 파일:

```text
api/market_data_service.py
tests/test_market_data_service.py
```

핵심 함수:

```python
get_asset_universe()
resolve_asset_class_to_asset_code()
get_price_matrix()
get_fx_matrix()
validate_market_data_coverage()
```

---

## PR 3. 3년치 데이터 수집기

목표:

```text
3년치 가격 데이터를 DB에 저장한다.
```

작업 파일:

```text
api/data_collectors/base.py
api/data_collectors/yahoo_provider.py
api/data_collectors/collector.py
scripts/collect_historical_data.py
tests/test_market_data_collection.py
```

완료 기준:

```bash
PYTHONPATH=. python scripts/collect_historical_data.py
```

그리고 DB 확인:

```sql
SELECT asset_code, COUNT(*), MIN(price_date), MAX(price_date)
FROM market_prices
GROUP BY asset_code;
```

---

## PR 4. BacktestEngine 추가

목표:

```text
실제 가격 기반으로 포트폴리오를 시뮬레이션한다.
```

작업 파일:

```text
api/backtest_engine.py
api/strategy_allocator.py
tests/test_backtest_engine.py
```

이 단계에서는 아직 API를 교체하지 말고 엔진 단위 테스트만 통과시키는 게 좋습니다.

---

## PR 5. `run_backtest()` 실제 엔진으로 교체

목표:

```text
기존 가정수익률 기반 백테스트를 실제 가격 기반 백테스트로 교체한다.
```

작업 파일:

```text
api/services.py
api/models.py
tests/test_api_backtests.py
tests/test_api_backtests_real_data.py
```

제거 또는 격리할 함수:

```text
_annual_return_for_asset()
_simulate_backtest_points()
_BACKTEST_ANNUAL_RETURNS
```

완전히 삭제하기보다 첫 단계에서는 fallback 또는 legacy 테스트용으로 격리해도 됩니다.

---

## PR 6. 시장 데이터 API 추가

목표:

```text
프론트에서 데이터 수집 상태를 확인하고 수집을 실행할 수 있게 한다.
```

작업 파일:

```text
api/main.py
api/models.py
api/market_data_service.py
tests/test_api_market_data.py
```

추가 API:

```text
GET  /api/market-data/assets
GET  /api/market-data/coverage
POST /api/market-data/collect
```

---

## PR 7. 프론트엔드 연결

목표:

```text
/backtests 화면에서 데이터 수집, 커버리지 확인, 실제 백테스트 실행을 연결한다.
```

작업 파일:

```text
web/app/backtests/BacktestsPageClient.tsx
web/lib/api.ts
web/lib/types.ts
```

검증:

```bash
cd web
npm run lint
npm run build
```

---

# 12. MVP 범위 제안

처음부터 완성형으로 만들면 범위가 커집니다.
MVP는 아래까지만 잡는 게 적절합니다.

## MVP 포함

```text
최근 3년치 가격 수집
자산군 → 대표 자산 매핑
초기자본 기반 가상 매수
월간/분기/주간 리밸런싱
KRW 기준 평가
USD 자산 환율 반영
총수익률
연환산수익률
MDD
변동성
백테스트 실행 이력 저장
자산곡선/drawdown 표시
```

## MVP 제외

```text
세금 상세 계산
배당금 별도 처리
종목별 최소 주문 단위
계좌별 ISA/연금/IRP 제약
개별 종목 생존편향 보정
Monte Carlo
최적화 엔진
동적 매크로 전략 고도화
```

---

# 13. 특히 조심해야 할 부분

## 13-1. look-ahead bias

백테스트 시점이 `2024-01-01`이면 `2024-01-01`까지의 데이터만 사용해야 합니다.

금지:

```python
prices = get_all_prices_until_end_date()
allocator.allocate(prices)
```

허용:

```python
prices_until_now = get_prices_until(as_of_date)
allocator.allocate(as_of_date=as_of_date, prices=prices_until_now)
```

---

## 13-2. 현재 `get_target_deviations()` 직접 사용 금지

이 함수는 현재 포트폴리오 상태를 보는 용도입니다.
백테스트의 과거 포트폴리오 상태와 다릅니다.

따라서 기존 함수를 그대로 쓰지 말고, 내부 로직 중 필요한 부분만 순수 함수로 분리해야 합니다.

---

## 13-3. 데이터 부족 시 조용히 보정하지 말 것

예를 들어 SPY는 3년치가 있는데 TLT는 6개월치만 있으면 백테스트를 실행하지 않는 게 맞습니다.

응답 예:

```json
{
  "code": "MARKET_DATA_COVERAGE_INSUFFICIENT",
  "message": "백테스트에 필요한 가격 데이터가 부족합니다.",
  "userAction": "TLT의 2023-05-24 ~ 2026-05-24 데이터를 먼저 수집하세요."
}
```

---

## 13-4. 수수료/슬리피지는 반드시 파라미터화

하드코딩하지 않는 게 좋습니다.

```text
feeBps
slippageBps
taxBps
```

이렇게 요청값 또는 설정값으로 받는 구조가 낫습니다.

---

# 14. 최종 개발 완료 기준

이 기능이 제대로 구현됐다고 볼 수 있는 기준은 다음입니다.

```text
1. /backtests 화면에서 초기자본, 기간, 리밸런싱 주기, 목표비중을 입력할 수 있다.
2. N년치 가격 데이터가 없으면 실행이 차단된다.
3. 데이터 수집 버튼으로 필요한 가격 데이터를 저장할 수 있다.
4. 백테스트 실행 시 외부 API를 호출하지 않는다.
5. 각 리밸런싱 시점마다 allocator가 목표비중을 반환한다.
6. 목표비중대로 가상 매수/매도가 발생한다.
7. 포트폴리오 가치는 실제 과거 가격과 환율로 평가된다.
8. 결과는 backtest_runs, backtest_points, backtest_positions, backtest_trades에 저장된다.
9. UI에서 총수익률, 연환산수익률, MDD, 변동성, 자산곡선, drawdown을 확인할 수 있다.
10. 테스트에서 가격 seed 데이터 기준으로 예상 수익률이 재현된다.
```

---

# 결론

현재 TripleA는 백테스트의 **API/UI/저장 골격**은 이미 있습니다.
하지만 사용자가 원하는 기능, 즉 **초기자본을 실제 과거 데이터 위에서 TripleA 자산 분배 알고리즘대로 운용했을 때의 수익률 검증**은 아직 구현되지 않았습니다.

개발 방향은 다음 순서가 가장 안전합니다.

```text
1. market_prices / fx_rates / asset_universe 추가
2. N년치 데이터 수집기 추가
3. StrategyAllocator 인터페이스로 자산 분배 알고리즘 분리
4. BacktestEngine 추가
5. run_backtest()를 실제 가격 기반 엔진으로 교체
6. 시장 데이터 coverage API 추가
7. /backtests UI에 데이터 수집/검증/실행 흐름 연결
```

첫 구현은 `static_target` 백테스트로 시작하고, 그다음 현재 TripleA의 리밸런싱·위험예산 로직을 `TripleAAllocator`로 분리해 붙이는 순서를 권장합니다.
