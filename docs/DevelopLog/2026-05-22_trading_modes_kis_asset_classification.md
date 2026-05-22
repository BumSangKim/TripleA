# 2026-05-22 KIS 보유상품 자산군 분류

## 기준 문서

- `docs/DevelopPlans/trading-modes-development-plan.md`
- `docs/DevelopLog/2026-05-22_trading_modes_kis_error_details.md`

## 이번 개발 단위

KIS 모의투자 계좌 동기화 시 모든 보유상품을 `국내주식`으로 저장하던 단순화를 제거하고, 상품명 기반으로 `국내주식`, `ETF`, `채권`을 분류해 리밸런싱과 계좌 스냅샷 집계에 반영했다.

## 작업 내용

### KIS 상품 분류 규칙 추가
- `api/kis.py`에 `classify_kis_asset(code, name)`을 추가했다.
- `KODEX`, `TIGER`, `ACE`, `SOL`, `PLUS`, `HANARO`, `KBSTAR`, `ARIRANG`, `RISE` 등 국내 ETF 브랜드를 `ETF`로 분류한다.
- `채권`, `국고채`, `국채`, `회사채`, `통안채`, `단기금융`, `MMF`, `CD금리`, `KOFR` 등 채권/현금성 키워드는 `채권`으로 우선 분류한다.
- 그 외 국내 종목은 `국내주식`으로 분류한다.

### 저장 로직 반영
- `KISPosition`에 `asset_class`를 추가했다.
- `parse_domestic_balance()`가 포지션별 자산군을 계산하고 스냅샷의 `domestic_stock_value`, `etf_value`, `bond_value`를 각각 집계한다.
- `api/providers.py`의 KIS snapshot upsert가 `holdings.asset_class`와 `account_snapshots`의 국내주식/ETF/채권 값을 저장하도록 바꿨다.

### 테스트 추가
- 삼성전자, KODEX 200, ACE 국고채10년 샘플로 분류 규칙을 검증했다.
- Paper provider sync 저장 테스트에서 holdings 자산군과 snapshot bucket 값이 DB에 반영되는지 확인했다.

### 레거시 확인
- `backend/`, `ingestion/`, `storage/`, `engine/`, `agents/` 디렉터리는 다시 생성되지 않았다.
- 레거시 경제지표 파이프라인 코드는 복구하지 않았다.

## 검증 결과

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_kis_provider.py
# 5 passed

PYTHONPATH=. .venv/bin/python -m pytest
# 71 passed, 1 warning

cd web && npm run lint
# passed

cd web && npm run build
# passed

git diff --check
# passed
```

## 미작업 내용

- 실제 KIS 모의투자 응답의 상품명 다양성에 맞춰 ETF/ETN/리츠/원자재 등 분류 규칙을 더 세분화할 필요가 있다.
- `LiveTradingProvider`의 실계좌 조회 전용 동기화는 아직 미구현이다.
- Paper 모드 주문 후보 생성, 주문 전 수동 승인, 주문 로그는 아직 구현하지 않았다.

## 다음 실행 가이드

1. `LiveTradingProvider.sync_accounts()`를 KIS 실계좌 조회 전용으로 연결한다.
2. Live 동기화 계좌는 `data_source='KIS_LIVE'`, `trade_status='LIVE_READ_ONLY'`로 저장한다.
3. 실계좌 주문은 계속 비활성화하고, 조회/스냅샷 저장까지만 테스트한다.
