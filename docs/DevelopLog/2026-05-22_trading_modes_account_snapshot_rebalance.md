# 2026-05-22 트레이딩 모드 계좌 스냅샷/리밸런싱 로그 구현

## 기준 문서

- `docs/DevelopPlans/trading-modes-development-plan.md`

## 이번 개발 단위

모드 기반 대시보드 고도화 중 한 번에 검증하기 좋은 백엔드 단위로, 계좌 정책 조회, 수동 계좌 스냅샷 저장, 리밸런싱 포함 여부 변경, 리밸런싱 실행 결과 저장 API를 구현했다.

## 작업 내용

### 계좌 정책 API
- `account_policies` 테이블의 계좌 유형별 정책을 조회하는 `GET /api/account-policies` 엔드포인트를 추가했다.
- 응답 모델 `AccountPolicyItem`을 추가해 계좌 타입, 역할, 입출금 가능 여부, 주문 가능 여부, 세제 혜택, 설명을 명시적으로 반환한다.

### 수동 계좌 스냅샷 API
- `POST /api/accounts/{account_id}/manual-snapshot` 엔드포인트를 추가했다.
- 수동 입력 스냅샷을 `account_snapshots`에 저장하고, 해당 계좌의 `total_value`, `cash`, `data_source`, `last_synced_at`을 함께 갱신한다.
- `GET /api/accounts/{account_id}/snapshots` 엔드포인트로 최근 스냅샷 목록을 조회할 수 있게 했다.
- `paper/live/backtest` 모드에서는 저장을 허용하고, `mock/test` 모드에서는 쓰기를 차단한다.

### 리밸런싱 포함 여부 API
- `PATCH /api/accounts/{account_id}/rebalancing-inclusion` 엔드포인트를 추가했다.
- 계좌별 `include_in_rebalancing` 값을 변경하고 갱신된 계좌 요약을 반환한다.
- 사용자 데이터 변경으로 간주해 `mock/test` 모드에서는 차단한다.

### 리밸런싱 실행 결과 저장
- `POST /api/rebalancing/run` 엔드포인트를 추가했다.
- 기존 리밸런싱 제안 계산 결과를 `rebalance_results` 테이블에 저장한다.
- 저장 항목에는 모드, 계좌 ID, 자산군, 현재 비중, 목표 비중, 괴리, 권장 액션, 권장 금액, 사유, 실행 여부가 포함된다.
- `GET /api/rebalancing/results` 엔드포인트로 최근 리밸런싱 결과 이력을 조회할 수 있게 했다.

### 테스트 추가
- `tests/test_api_endpoints.py`에 계좌 정책, 수동 스냅샷, 쓰기 차단, 리밸런싱 포함 여부, 리밸런싱 결과 저장 테스트를 추가했다.

## 검증 결과

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_api_endpoints.py tests/test_modes.py
# 39 passed, 1 warning

PYTHONPATH=. .venv/bin/python -m pytest
# 169 passed, 1 warning

cd web && npm run build
# passed
```

추가로 `ensure_dashboard_tables()` 실행 후 `account_policies`, `account_snapshots`, `rebalance_results` 테이블 생성 여부와 정책 시드 4건을 확인했다.

## 미작업 내용

- `ProviderRouter`와 실제 데이터 공급자 구현: Mock/Test/Backtest/Paper/Live별 계좌·시세 조회 라우팅은 아직 API 서비스 내부에 직접 연결되지 않았다.
- 백테스트 실행 엔진: 기간 선택, 과거 스냅샷 기반 리밸런싱 시뮬레이션, `backtest_runs` 저장 로직은 아직 미구현이다.
- 주문 후보/수동 승인 API: 실전 모드는 조회 전용 정책을 유지해야 하며, 주문은 후보 생성과 수동 승인 흐름으로 별도 구현이 필요하다.
- 프론트엔드 계좌 관리 UI: 수동 스냅샷 입력 모달, 계좌 정책 표시, 리밸런싱 포함 토글, 리밸런싱 결과 이력 화면은 아직 연결되지 않았다.
- 텔레그램 알림 서비스: 리밸런싱 필요/연동 실패/주문 후보 생성 알림과 중복 방지 정책은 DB 스키마만 준비된 상태다.
- 계좌별 엔진 구현: `ISAAccountEngine`, `PensionSavingsEngine`, `IRPEngine`, `GeneralAccountEngine`의 정책별 리밸런싱 차등 적용은 아직 기본 룰 기반 제안 수준이다.
- 프론트엔드 lint 정리: 기존 React hook dependency/unused variable lint 이슈가 남아 있어 별도 정리가 필요하다.

## 다음 실행 가이드

1. 프론트엔드에서 모드 선택값을 주요 API 요청에 전달하고, 계좌 화면에 수동 스냅샷 입력과 리밸런싱 포함 토글을 연결한다.
2. `ProviderRouter` 인터페이스를 먼저 만들고, Mock/Test는 현재 DB/fixture, Paper는 한국투자증권 모의투자 조회, Live는 조회 전용 provider로 분리한다.
3. 리밸런싱 결과 이력 화면을 붙인 뒤, 동일 실행의 중복 저장 방지를 위해 `run_id` 또는 실행 배치 개념을 추가한다.
4. 주문 관련 구현 전에는 `live` 모드 기본 정책을 계속 `order_enabled=false`, `requires_manual_approval=true`로 유지한다.
