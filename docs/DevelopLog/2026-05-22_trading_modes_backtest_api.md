# 2026-05-22 Backtest API 및 결과 저장

## 작업 범위

`trading-modes-development-plan.md`의 백테스트 항목 중 주문과 외부 브로커 호출이 없는 실행/저장 레이어를 구현했다. 사용자 요청에 따라 실전 투자와 모의 투자 항목은 이번 실행 단위에서 제외했다.

## 작업 내용

- `backtest_points` 테이블을 추가해 백테스트 실행별 자산곡선과 drawdown 시계열을 저장한다.
- `BacktestRunRequest`, `BacktestRunResponse`, `BacktestPoint`, `BacktestTarget` 스키마를 추가했다.
- `POST /api/backtests/run`을 추가했다.
  - `startDate`, `endDate`, `initialCapital`, `rebalanceFrequency`, `targets`를 입력받는다.
  - `weekly`, `monthly`, `quarterly` 리밸런싱 간격을 지원한다.
  - 목표 비중이 비어 있으면 DB의 `targets` 중 `asset_allocation`을 사용한다.
  - 결과는 `backtest_runs`와 `backtest_points`에 저장한다.
- `GET /api/backtests/runs`, `GET /api/backtests/runs/{run_id}`를 추가해 실행 이력과 상세 자산곡선을 조회할 수 있게 했다.
- 백테스트 API 테스트를 추가했다.
  - 실행 결과 저장
  - 기본 목표 비중 fallback
  - 상세/목록 조회
  - 잘못된 날짜 요청 거부
- `README.md`의 주요 API와 검증 명령을 최신 상태로 갱신했다.

## 미작업 내용

- 백테스트 화면은 아직 없다. 다음 실행 단위에서 `/backtests` 페이지, 사이드바 링크, 기간/초기자본/목표비중 입력, 결과 차트 표시를 연결한다.
- 현재 백테스트 수익률은 과거 실시세 기반이 아니라 자산군별 보수적 연간 가정치와 결정론적 변동 패턴을 사용한다. 과거 가격/스냅샷 데이터가 준비되면 실제 시계열 기반 엔진으로 교체한다.
- 알림 채널과 `notification_logs` 중복 방지 정책은 아직 미연결이다.

## 레거시 확인

- 루트 2단계 깊이에서 `backend`, `ingestion`, `storage`, `engine`, `agents`, `collectors` 디렉터리가 남아 있지 않음을 확인했다.
- 레거시 경제지표 수집 파이프라인, 실전 주문, 모의 주문 실행 로직은 추가하거나 복구하지 않았다.

## 검증

- `PYTHONPATH=. .venv/bin/python -m pytest tests/test_api_backtests.py` 통과
- `PYTHONPATH=. .venv/bin/python -m pytest` 통과: 80 passed, 1 warning
- `cd web && npm run lint` 통과
- `cd web && npm run build` 통과

## 다음 실행 참고

1. `web/app/backtests` 페이지를 추가한다.
2. `POST /api/backtests/run`과 `GET /api/backtests/runs`를 프론트에서 호출한다.
3. 자산곡선과 drawdown을 같은 화면에서 확인할 수 있게 차트 컴포넌트를 만든다.
4. Browser로 `/backtests` 화면을 열어 데스크톱/모바일 렌더링을 확인한다.
