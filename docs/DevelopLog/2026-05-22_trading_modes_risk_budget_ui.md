# 2026-05-22 RiskBudget UI 연결

## 작업 범위

직전 단위에서 추가한 `GET /api/engine/risk-budget`를 포트폴리오 화면에 연결했다. 실전 투자와 모의 투자 주문 항목은 제외했다.

## 작업 내용

- 프론트 타입에 `RiskBudgetItem`을 추가했다.
- `api.getRiskBudget` 클라이언트 함수를 추가했다.
- 포트폴리오 화면에 `위험예산` 섹션을 추가했다.
  - 전략 버킷명
  - 현재/목표 비중
  - 최소/최대 허용 범위
  - `유지/보강/축소` 액션
  - `normal/warning/danger` 상태 색상
- 포트폴리오 화면의 API 호출을 `Promise.allSettled`로 바꿔, 대시보드 요약 호출이 실패해도 위험예산 섹션은 독립적으로 표시되게 했다.

## 미작업 내용

- 위험예산 초과 상태에서 리밸런싱 후보 금액을 자동 제한하는 기능은 아직 없다.
- 계좌 유형별 엔진 결과를 화면에서 구분하는 UI는 아직 없다.
- 위험예산 목표값을 UI에서 수정하는 기능은 아직 없다.

## 레거시 확인

- 레거시 수집 파이프라인이나 주문 실행 스크립트는 추가하지 않았다.
- 변경 범위는 포트폴리오 화면, 프론트 API 타입, 개발 로그로 제한했다.

## 검증

- `PYTHONPATH=. .venv/bin/python -m pytest tests/test_api_engine.py` 통과
- `cd web && npm run lint` 통과
- `cd web && npm run build` 통과
- Browser에서 `http://localhost:3000/portfolio`를 열어 위험예산 섹션이 렌더링되는 것을 확인했다.

## 다음 실행 참고

1. 위험예산 목표값 수정 API/UI를 추가한다.
2. 계좌별 엔진 분리를 진행한다.
3. 남은 비거래 미완료 항목을 계획서 기준으로 다시 점검한다.
