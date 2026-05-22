# 2026-05-22 Live Provider 조회 전용 동기화

## 기준 문서

- `docs/DevelopPlans/trading-modes-development-plan.md`
- `docs/DevelopLog/2026-05-22_trading_modes_kis_asset_classification.md`

## 이번 개발 단위

`LiveTradingProvider`를 KIS 실계좌 조회 전용 동기화로 연결했다. 실계좌 주문 실행은 구현하지 않고, 잔고 조회, 계좌/보유상품/스냅샷 저장, UI 동기화 버튼 활성화까지만 범위를 제한했다.

## 작업 내용

### Live provider sync 구현
- `LiveTradingProvider.sync_accounts()`를 구현했다.
- `load_kis_config(force_demo=False)`로 실전투자용 KIS 설정을 읽는다.
- KIS 국내 잔고 조회 결과를 기존 KIS snapshot upsert 경로로 저장한다.
- 저장 계좌는 `data_source='KIS_LIVE'`, `trade_status='LIVE_READ_ONLY'`로 명확히 표시한다.
- Paper provider와 마찬가지로 `accountMasked`, 동기화 종목 수, 총자산, 현금 값을 반환한다.

### 계좌 화면 연결
- 계좌 화면의 `KIS 동기화` 버튼을 `paper`와 `live` 모드에서 활성화하도록 확장했다.
- Mock/Test/Backtest에서는 계속 비활성화된다.
- 실패 메시지는 직전 단위에서 만든 구조화된 오류 메시지를 그대로 사용한다.

### 문서/테스트
- `README.md` API 표에 `/api/providers/live/sync-accounts`를 추가했다.
- Live provider가 KIS 실계좌 설정을 사용하고 `KIS_LIVE`, `LIVE_READ_ONLY`로 저장하는 테스트를 추가했다.

### 레거시 확인
- `backend/`, `ingestion/`, `storage/`, `engine/`, `agents/` 디렉터리는 다시 생성되지 않았다.
- 실계좌 주문 로직이나 레거시 주문 스크립트는 추가하지 않았다.

## 검증 결과

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_kis_provider.py tests/test_modes.py
# 13 passed

cd web && npm run lint
# passed

PYTHONPATH=. .venv/bin/python -m pytest
# 72 passed, 1 warning

cd web && npm run build
# passed

git diff --check
# passed
```

## 미작업 내용

- 실제 KIS 실계좌 API 호출은 로컬 실계좌 환경변수 설정 후 사용자가 직접 확인해야 한다.
- Paper 모드 주문 후보 생성, 주문 전 수동 승인, 주문 로그는 아직 구현하지 않았다.
- Live 모드는 계속 조회 전용이며, 수동 승인 주문 단계는 별도 설계/테스트가 필요하다.
- KIS 상품 분류는 ETF/채권/국내주식 중심이며 리츠/원자재/ETN 등 세부 분류는 후속 확장이 필요하다.

## 다음 실행 가이드

1. 주문을 바로 실행하지 않는 `order_candidates`/`order_logs` 스키마를 추가한다.
2. 리밸런싱 결과를 기반으로 Paper 모드 주문 후보만 생성한다.
3. 실제 주문 API 호출 전에는 수동 승인 상태와 별도 안전장치를 둔다.
