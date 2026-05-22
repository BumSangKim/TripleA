# 2026-05-22 프론트엔드 Lint 품질 게이트 복구

## 기준 문서

- `docs/DevelopPlans/trading-modes-development-plan.md`
- `docs/DevelopLog/2026-05-22_trading_modes_kis_sync_ui.md`

## 이번 개발 단위

직전 단위에서 미작업으로 남긴 프론트엔드 lint 오류를 정리했다. 신규 기능을 추가하기보다는 다음 KIS/Live provider 연동 작업 전에 `lint`, `build`, `pytest`가 모두 통과하는 상태를 회복하는 데 범위를 제한했다.

## 작업 내용

### React effect lint 정리
- `AlertsPageClient.tsx`, `DocumentsPageClient.tsx`, `MacroPageClient.tsx`, `TargetsPageClient.tsx`, `MemoPanel.tsx`의 초기 로딩/복원 effect를 React lint 규칙에 맞게 조정했다.
- 마운트 직후 API 호출 또는 localStorage 복원에서 발생하던 동기 setState 경고를 `setTimeout` 기반 지연 실행으로 정리했다.
- 반복 호출 함수는 `useCallback`으로 고정해 effect dependency를 명확히 했다.

### 렌더 중 변수 재할당 제거
- `PortfolioPageClient.tsx` 도넛 차트에서 렌더 중 `cumulative`를 재할당하던 계산을 누적 전 비중 계산 방식으로 바꿨다.
- `AccountPanel.tsx` 도넛 차트에서도 렌더 중 `cum` 재할당을 제거했다.

### TypeScript/Unused 정리
- `AlertsPageClient.tsx`의 `StatusChip`에 `any` 캐스팅 없이 `AlertItem.level` 타입을 전달하도록 수정했다.
- `PortfolioPageClient.tsx`, `KPIBar.tsx`, `MetricCard.tsx`의 사용하지 않는 import/변수를 제거했다.
- `KPIBar.tsx`의 리스크 레벨 `"낙음"` 오타를 `"낮음"`으로 수정했다.

### 레거시 확인
- `backend/`, `ingestion/`, `storage/`, `engine/`, `agents/` 디렉터리는 다시 생성되지 않았다.
- 이번 단위는 레거시 파일을 새로 만들거나 복구하지 않았다.

## 검증 결과

```bash
cd web && npm run lint
# passed

cd web && npm run build
# passed

PYTHONPATH=. .venv/bin/python -m pytest
# 68 passed, 1 warning

git diff --check
# passed
```

## 미작업 내용

- 실제 KIS 모의투자 API 호출은 로컬 환경변수 설정 후 계좌 화면에서 수동 검증이 필요하다.
- KIS paper 동기화 실패 메시지를 설정 누락, KIS API 오류, 네트워크 오류로 세분화하는 UI가 필요하다.
- KIS 보유상품 자산군 분류 규칙은 아직 단순화되어 있다.
- `LiveTradingProvider`의 실계좌 조회 전용 동기화는 아직 미구현이다.
- Paper 모드 주문 후보 생성, 주문 전 수동 승인, 주문 로그는 아직 구현하지 않았다.

## 다음 실행 가이드

1. KIS provider 오류를 구조화해서 API 응답과 계좌 화면 메시지에 반영한다.
2. KIS 보유상품의 ETF/채권형 ETF/국내주식 분류 규칙을 추가한다.
3. 이후 `LiveTradingProvider`를 조회 전용으로 연결하되, 주문 기능은 계속 비활성화한다.
