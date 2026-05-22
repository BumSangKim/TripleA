# 2026-05-22 주문 후보/수동 승인 로그 API

## 기준 문서

- `docs/DevelopPlans/trading-modes-development-plan.md`
- `docs/DevelopLog/2026-05-22_trading_modes_live_read_only_sync.md`

## 이번 개발 단위

실제 브로커 주문 전송 없이, 리밸런싱 결과를 기반으로 주문 후보를 만들고 Paper 모드에서 수동 승인 로그까지만 남기는 API 골격을 추가했다. Live 모드는 주문 후보 생성은 가능하지만 `/api/orders/execute`에서 계속 차단된다.

## 작업 내용

### DB 스키마 추가
- `order_drafts` 테이블을 추가했다.
- `order_items` 테이블을 추가했다.
- `order_logs` 테이블을 추가했다.
- 기존 DB는 `CREATE TABLE IF NOT EXISTS` 경로로 보강되며 레거시 주문 스크립트는 복구하지 않았다.

### 주문 후보 생성
- `POST /api/orders/draft`를 추가했다.
- 요청: `{mode, source, maxOrderAmount}`.
- 현재는 `source='rebalancing'`만 지원한다.
- Paper/Live 모드에서만 주문 후보를 만들 수 있다.
- 자산군 목표 괴리(`TargetItem`)가 warning/danger인 항목만 후보로 만든다.
- 괴리가 양수이면 `SELL`, 음수이면 `BUY` 후보로 변환한다.
- `maxOrderAmount`가 있으면 후보별 금액을 상한 처리한다.

### 수동 승인 로그
- `POST /api/orders/execute`를 추가했다.
- Paper 모드에서 `confirmText='모의 주문을 승인합니다'`일 때만 승인 로그를 남긴다.
- 상태는 `APPROVED_NOT_SENT`로 저장한다.
- 실제 KIS 모의주문/실주문 API 호출은 아직 하지 않는다.
- Live 모드는 실계좌 보호를 위해 계속 HTTP 403으로 차단한다.

### 테스트 추가
- 주문 후보 생성과 금액 상한 적용을 검증했다.
- Mock 모드에서 주문 후보 생성이 거부되는지 확인했다.
- Paper 수동 승인 로그가 `order_logs`에 기록되는지 확인했다.
- Live execute가 계속 차단되는지 확인했다.

### 레거시 확인
- `backend/`, `ingestion/`, `storage/`, `engine/`, `agents/` 디렉터리는 다시 생성되지 않았다.
- 과거 주문/수집 파이프라인 파일은 복구하지 않았다.

## 검증 결과

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_api_orders.py
# 4 passed

PYTHONPATH=. .venv/bin/python -m pytest
# 76 passed, 1 warning

cd web && npm run lint
# passed

cd web && npm run build
# passed

git diff --check
# passed
```

## 미작업 내용

- 주문 후보/승인 상태를 보여주는 프론트엔드 화면은 아직 없다.
- KIS 모의주문 API 호출은 아직 구현하지 않았다.
- Live 실주문은 계속 비활성화되어 있으며, 수동 승인 주문 기능은 별도 안전장치와 함께 설계해야 한다.
- 주문 후보가 아직 자산군 단위이며, 개별 ETF/종목 단위 주문 수량 산출은 미구현이다.
- 현금/계좌별 주문 가능 금액 검증은 아직 없다.

## 다음 실행 가이드

1. 계좌 화면 또는 별도 주문 화면에 주문 후보 생성/승인 로그 UI를 추가한다.
2. Paper 모드에서만 모의주문 API 전송을 별도 실행 단위로 구현한다.
3. 주문 후보를 자산군 단위에서 실제 보유/목표 ETF 단위로 구체화한다.
