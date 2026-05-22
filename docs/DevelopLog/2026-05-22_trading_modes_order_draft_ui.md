# 2026-05-22 주문 후보 UI 연결

## 기준 문서

- `docs/DevelopPlans/trading-modes-development-plan.md`
- `docs/DevelopLog/2026-05-22_trading_modes_order_draft_api.md`

## 이번 개발 단위

직전 단위에서 추가한 주문 후보/수동 승인 로그 API를 프론트엔드에 연결했다. 실제 브로커 주문 전송 UI는 만들지 않고, 후보 생성과 Paper 승인 로그 기록까지만 다루는 별도 `/orders` 화면을 추가했다.

## 작업 내용

### API 클라이언트/타입
- `web/lib/types.ts`에 `OrderItem`, `OrderDraftResponse`를 추가했다.
- `web/lib/api.ts`에 `createOrderDraft()`, `executeOrderDraft()`를 추가했다.

### 주문 후보 화면
- `web/app/orders/page.tsx`와 `OrdersPageClient.tsx`를 추가했다.
- Paper/Live 모드 선택, 후보별 최대 주문 금액 입력, 후보 생성 버튼을 제공한다.
- 후보 생성 결과로 Draft ID, 상태, 총 후보 금액, 후보 목록을 표시한다.
- Paper 모드에서만 `Paper 승인 기록` 버튼이 활성화된다.
- Live 모드에서는 실제 주문 실행 비활성화 안내를 표시한다.

### 내비게이션
- 사이드바에 `/orders` 메뉴를 추가했다.

### 레거시 확인
- `backend/`, `ingestion/`, `storage/`, `engine/`, `agents/` 디렉터리는 다시 생성되지 않았다.
- 과거 주문 스크립트는 복구하지 않았다.

## 검증 결과

```bash
cd web && npm run lint
# passed

cd web && npm run build
# passed

PYTHONPATH=. .venv/bin/python -m pytest
# 76 passed, 1 warning

git diff --check
# passed
```

추가 확인:
- `curl http://127.0.0.1:3000/orders`로 서버 렌더 HTML에 `/orders`, `주문 후보`, `후보 생성`, `Paper 승인 기록`이 포함되는 것을 확인했다.
- Codex in-app Browser에서 `http://127.0.0.1:3000/orders`를 열고 같은 UI 요소가 노출되는 것을 확인했다.

## 미작업 내용

- KIS 모의주문 API 실제 전송은 아직 구현하지 않았다.
- Live 실주문은 계속 비활성화되어 있다.
- 주문 후보는 자산군 단위이며, 실제 ETF/종목 단위 수량 산출은 아직 없다.
- 주문 후보 이력 조회 API와 과거 draft 목록 UI는 아직 없다.
- 계좌별 현금/주문 가능 금액 검증은 아직 없다.

## 다음 실행 가이드

1. `/api/orders` 조회 API와 주문 후보 이력 UI를 추가한다.
2. 후보를 자산군 단위에서 실제 매수/매도 대상 ETF 또는 종목 단위로 구체화한다.
3. Paper 모드 KIS 모의주문 전송은 별도 안전장치와 테스트를 추가한 뒤 구현한다.
