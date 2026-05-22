# 2026-05-22 Backtest UI 연결

## 작업 범위

`trading-modes-development-plan.md`의 백테스트 UI 항목을 구현했다. 이번 실행 단위 역시 실전 투자와 모의 투자 주문 항목은 제외하고, 저장된 백테스트 결과를 조회·표시하는 화면에만 집중했다.

## 작업 내용

- `/backtests` 페이지를 추가했다.
- 사이드바에 `백테스트` 메뉴를 추가했다.
- 프론트 타입과 API 래퍼를 추가했다.
  - `BacktestRunRequest`
  - `BacktestRunResponse`
  - `BacktestPoint`
  - `api.runBacktest`
  - `api.getBacktestRuns`
- 백테스트 입력 화면을 구성했다.
  - 이름, 시작일, 종료일, 초기자본, 리밸런싱 주기
  - 자산군별 목표 비중 행 추가/삭제
  - 목표 비중 합계 표시
- 결과 화면을 구성했다.
  - 총수익률, 연환산 수익률, MDD, 변동성
  - 자산곡선 SVG 차트
  - Drawdown SVG 차트
  - 최근 실행 이력 테이블과 결과 재선택

## 미작업 내용

- 과거 실제 가격 데이터 기반 백테스트 엔진은 아직 없다. 현재는 API 단위에서 만든 자산군별 결정론적 시뮬레이션 결과를 표시한다.
- 자산군 프리셋과 저장된 전략 템플릿 기능은 아직 없다.
- 모바일 전용 사이드바 접힘/하단 내비게이션은 아직 없다.
- 알림 채널과 `notification_logs` 중복 방지 정책은 아직 미연결이다.

## 레거시 확인

- 레거시 경제지표 수집 파이프라인이나 주문 실행 스크립트는 추가하지 않았다.
- 이번 변경은 `web/app/backtests`, `web/lib`, `web/components/layout` 범위의 새 백테스트 화면 연결로 제한했다.

## 검증

- `cd web && npm run lint` 통과
- `cd web && npm run build` 통과
- Browser에서 `http://localhost:3000/backtests`를 열어 화면 렌더링을 확인했다.
- Browser에서 `실행` 버튼을 눌러 `POST /api/backtests/run` 호출, 결과 저장, 지표/차트/이력 표시를 확인했다.

## 다음 실행 참고

1. 실제 과거 가격 데이터 소스가 준비되면 백테스트 서비스의 결정론적 수익률 가정을 시계열 기반 계산으로 교체한다.
2. 알림 채널/중복 방지 정책을 `notification_logs`에 연결한다.
3. 전체 계획서에서 실전/모의 투자 제외 후 남은 비거래 미완료 항목을 다시 점검한다.
