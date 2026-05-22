# 2026-05-22 KIS Paper 동기화 UI 연결

## 기준 문서

- `docs/DevelopPlans/trading-modes-development-plan.md`

## 이번 개발 단위

직전 단위에서 구현한 `POST /api/providers/paper/sync-accounts`를 계좌 화면에서 바로 실행할 수 있도록 연결했다. 이번 범위는 Paper 모드의 읽기 전용 KIS 모의투자 계좌 동기화 UI, 성공/실패 메시지, 동기화 후 화면 재조회까지로 제한했다.

## 작업 내용

### 프론트엔드 API 클라이언트 연결
- `web/lib/types.ts`에 `ProviderSyncResult` 타입을 추가했다.
- `web/lib/api.ts`에 `api.syncProviderAccounts(mode)`를 추가했다.
- API 응답 타입은 계좌 ID, 마스킹 계좌번호, 동기화 종목 수, 총자산, 현금 값을 포함한다.

### 계좌 화면 KIS 동기화 액션 추가
- `web/app/accounts/AccountsPageClient.tsx`에 `KIS 동기화` 버튼을 추가했다.
- 버튼은 `paper` 모드에서만 활성화되고, 다른 모드에서는 비활성화된다.
- 동기화 실행 중에는 `동기화 중...` 상태로 표시한다.
- 성공 시 마스킹 계좌번호, 동기화 종목 수, 총자산을 화면 메시지로 표시한다.
- 실패 시 API 키, 시크릿, 전체 계좌번호를 노출하지 않고 API 클라이언트의 일반 오류 메시지만 표시한다.
- 성공 후 계좌 목록, 리밸런싱 로그, 선택 계좌 상세/스냅샷을 다시 불러온다.

### 레거시 확인
- `backend/`, `ingestion/`, `storage/`, `engine/`, `agents/` 디렉터리는 다시 생성되지 않았다.
- 레거시 경로 문자열은 이전 개발 로그의 삭제 내역 설명에만 남아 있다.

## 검증 결과

```bash
PYTHONPATH=. .venv/bin/python -m pytest
# 68 passed, 1 warning

cd web && npm run build
# passed

git diff --check
# passed
```

추가 확인:
- `npm run lint`는 실패했다. 실패 위치는 기존에 남아 있던 `AlertsPageClient.tsx`, `DocumentsPageClient.tsx`, `MacroPageClient.tsx`, `PortfolioPageClient.tsx`, `TargetsPageClient.tsx`, `dashboard/*`, `MetricCard.tsx`의 React/TypeScript lint 항목이며, 이번 변경 파일인 `AccountsPageClient.tsx`는 실패 목록에 없다.
- Next dev 서버에서 `/accounts` HTML을 확인했고, Paper 모드 기본 화면에 `KIS 동기화` 버튼이 렌더링되는 것을 확인했다.
- Codex in-app Browser는 로컬 dev 서버 네트워크 접근이 차단되어 실제 클릭 검증은 수행하지 못했다. 동기화 버튼 클릭은 실제 KIS API 호출과 DB 쓰기를 유발할 수 있어 이번 단위에서는 자동 클릭 검증 범위에서 제외했다.

## 미작업 내용

- 실제 KIS 모의투자 API 호출은 로컬 환경변수 설정 후 계좌 화면에서 수동 검증이 필요하다.
- 동기화 실패 원인을 설정 누락, KIS API 오류, 네트워크 오류로 나누어 더 친절하게 표시하는 UI가 필요하다.
- `LiveTradingProvider`의 실계좌 조회 전용 동기화는 아직 미구현이다.
- KIS 보유상품을 ETF/채권형 ETF/국내주식 등으로 분류하는 자산군 매핑은 아직 단순화되어 있다.
- 프론트엔드 lint 오류 정리는 별도 실행 단위로 남아 있다.
- Paper 모드 주문 후보 생성, 주문 전 수동 승인, 주문 로그는 아직 구현하지 않았다.

## 다음 실행 가이드

1. 프론트엔드 lint 오류를 작은 단위로 정리해 CI 품질 기준을 회복한다.
2. KIS paper 동기화 실패 상태를 계좌 화면에 세분화해서 표시한다.
3. KIS 보유상품 자산군 분류 규칙을 추가하고 리밸런싱 결과의 정확도를 높인다.
4. 이후 `LiveTradingProvider`는 우선 조회 전용으로만 연결하고 `trade_status='LIVE_READ_ONLY'`를 명확히 유지한다.
