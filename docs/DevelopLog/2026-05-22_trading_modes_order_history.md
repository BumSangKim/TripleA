# 2026-05-22 주문 Draft 이력 조회

## 기준 문서

- `docs/DevelopPlans/trading-modes-development-plan.md`
- `docs/DevelopLog/2026-05-22_trading_modes_order_draft_ui.md`

## 이번 개발 단위

생성한 주문 후보 draft를 다시 조회할 수 있도록 API와 `/orders` 화면 이력 섹션을 추가했다. 이번 단위도 실제 브로커 주문 전송과는 분리되어 있으며, 후보/승인 로그 관리 기능만 다룬다.

## 작업 내용

### API
- `GET /api/orders/drafts`를 추가했다.
- `mode`와 `limit` 쿼리 파라미터를 지원한다.
- 각 draft는 후보 item 목록을 포함한 `OrderDraftResponse` 형태로 반환한다.

### 서비스
- `list_order_drafts()`를 추가했다.
- 최신 draft부터 조회하고, 기존 `_order_draft_response()`를 재사용해 응답 형태를 일관되게 유지했다.

### 프론트엔드
- `api.getOrderDrafts()`를 추가했다.
- `/orders` 화면에 `최근 Draft` 테이블을 추가했다.
- mode 변경 시 해당 모드의 최근 draft를 다시 조회한다.
- 이력의 `보기` 버튼으로 과거 draft를 현재 후보 목록에 다시 표시할 수 있게 했다.

### 테스트
- 주문 draft 생성 후 `GET /api/orders/drafts?mode=paper`가 최신 draft와 item 목록을 반환하는지 검증했다.

### 레거시 확인
- `backend/`, `ingestion/`, `storage/`, `engine/`, `agents/` 디렉터리는 다시 생성되지 않았다.
- 레거시 주문 스크립트는 복구하지 않았다.

## 검증 결과

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_api_orders.py
# 5 passed

cd web && npm run lint
# passed

PYTHONPATH=. .venv/bin/python -m pytest
# 77 passed, 1 warning

cd web && npm run build
# passed

git diff --check
# passed
```

추가 확인:
- Codex in-app Browser에서 `http://127.0.0.1:3000/orders`를 열고 `최근 Draft`, `후보 생성` 섹션이 노출되는 것을 확인했다.

## 미작업 내용

- KIS 모의주문 API 실제 전송은 아직 구현하지 않았다.
- Live 실주문은 계속 비활성화되어 있다.
- 주문 후보는 아직 자산군 단위이며 실제 ETF/종목 단위 주문 수량 산출은 미구현이다.
- 계좌별 현금/주문 가능 금액 검증은 아직 없다.

## 다음 실행 가이드

1. 주문 후보를 자산군 단위에서 실제 매매 대상 ETF/종목 단위로 구체화한다.
2. 계좌별 현금/주문 가능 금액 검증을 추가한다.
3. Paper 모드 KIS 모의주문 전송은 별도 안전장치와 테스트를 추가한 뒤 구현한다.
