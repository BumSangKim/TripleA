# 2026-05-22 트레이딩 모드 계좌 화면 연결

## 기준 문서

- `docs/DevelopPlans/trading-modes-development-plan.md`

## 이번 개발 단위

직전 단위에서 구현한 계좌 정책, 수동 스냅샷, 리밸런싱 실행 결과 API를 Next.js 계좌 화면에 연결했다. 범위는 계좌 관리 화면에서 바로 검증 가능한 UI/API 연동으로 제한했다.

## 작업 내용

### 프론트엔드 API 클라이언트 확장
- `web/lib/types.ts`에 `AccountPolicyItem`, `AccountSnapshotCreate`, `AccountSnapshotItem`, `RebalanceResultItem`, `RebalanceRunResponse` 타입을 추가했다.
- `web/lib/api.ts`에 모드 쿼리 파라미터 지원 헬퍼를 추가했다.
- 계좌 정책 조회, 스냅샷 조회/저장, 리밸런싱 포함 여부 변경, 리밸런싱 실행/결과 조회 API 메서드를 추가했다.
- 기존 `getDashboardSummary()`는 선택적으로 `mode`를 받을 수 있게 확장했다.

### 계좌 화면 모드 연결
- `web/app/accounts/AccountsPageClient.tsx`에 `mock/test/backtest/paper/live` 모드 선택 컨트롤을 추가했다.
- 선택 모드를 `dashboard summary`, CSV 업로드, 스냅샷 저장, 리밸런싱 실행 요청에 반영했다.
- `mock/test`처럼 쓰기 불가 모드에서는 CSV 업로드, 수동 스냅샷 저장, 리밸런싱 실행 저장이 비활성화되도록 연결했다.

### 계좌 정책 표시
- `GET /api/account-policies` 결과를 계좌 화면의 정책 테이블로 표시했다.
- 계좌 목록의 계좌 유형과 정책 역할을 함께 보여주도록 했다.

### 수동 스냅샷 UI
- 계좌 선택 시 보유 종목과 최근 스냅샷 이력을 함께 조회하도록 했다.
- 총자산, 현금, 국내주식, 해외주식, 채권, ETF, 연금, 대체자산 입력 폼을 추가했다.
- 스냅샷 저장 후 계좌 요약과 스냅샷 이력을 다시 불러오도록 했다.

### 리밸런싱 실행 로그 UI
- 계좌 화면 하단에 `POST /api/rebalancing/run` 실행 버튼과 `GET /api/rebalancing/results` 결과 테이블을 추가했다.
- 실행 로그에는 시점, 자산군, 현재/목표 비중, 괴리, 액션, 금액을 표시한다.

## 검증 결과

```bash
PYTHONPATH=. .venv/bin/python -m pytest
# 169 passed, 1 warning

PYTHONPATH=. .venv/bin/python -m pytest tests/test_api_endpoints.py tests/test_modes.py
# 39 passed, 1 warning

cd web && npm run build
# passed
```

브라우저 검증:
- `http://127.0.0.1:3000/accounts` 렌더링 확인
- 계좌 정책 테이블 렌더링 확인
- 리밸런싱 실행 로그 영역 렌더링 확인
- `mock` 모드 선택 시 리밸런싱 저장 버튼 비활성화 확인

Lint:
- 이번에 수정한 `AccountsPageClient.tsx` 관련 lint 오류는 정리했다.
- `npm run lint` 전체 실행은 기존 다른 화면의 React hook/immutability/unused variable 오류 때문에 실패한다.

## 미작업 내용

- `ProviderRouter`와 모드별 DataProvider 실제 구현은 아직 미완료다.
- Paper/Live 계좌 조회를 한국투자증권 API provider로 직접 연결하는 작업은 아직 남아 있다.
- 백테스트 실행 UI와 `backtest_runs` 저장/조회 흐름은 아직 미구현이다.
- 리밸런싱 실행 로그는 현재 자산군 단위 결과 저장이며, 계좌별/전략 엔진별 결과 분리는 아직 적용되지 않았다.
- 주문 후보 생성, 수동 승인, 실제 주문 실행 차단/허용 정책 UI는 아직 미구현이다.
- 텔레그램 알림 중복 방지와 notification 로그 연동은 아직 UI/API에 연결되지 않았다.
- 기존 프론트엔드 lint 오류 정리는 별도 단위로 처리해야 한다.

## 다음 실행 가이드

1. `api/providers.py` 또는 유사 모듈로 `ProviderRouter`, `MockProvider`, `PaperTradingProvider`, `LiveTradingProvider` 인터페이스를 먼저 분리한다.
2. Paper provider는 기존 한국투자증권 모의투자 조회 스크립트의 인증/잔고 조회 로직을 서비스 계층으로 이동해 붙인다.
3. Live provider는 조회 전용으로 시작하고, 주문 관련 기능은 `requires_manual_approval=true` 정책을 유지한다.
4. 계좌 화면에 실제 계좌 연결 상태와 provider 오류 메시지를 표시하는 작은 상태 영역을 추가한다.
5. Provider 분리 후에는 `tests/test_modes.py`에 모드별 provider 선택, read/write 정책, 외부 API 차단 테스트를 추가한다.
