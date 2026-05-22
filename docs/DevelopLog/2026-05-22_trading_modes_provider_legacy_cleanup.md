# 2026-05-22 ProviderRouter 도입 및 레거시 정리

## 기준 문서

- `docs/DevelopPlans/trading-modes-development-plan.md`

## 이번 개발 단위

트레이딩 모드 계획서의 Provider 계층을 실제 코드에 추가하고, 새 구조와 충돌하던 과거 경제지표 수집 파이프라인 레거시 코드를 삭제했다. 실행 단위는 API 모드 라우팅 경계 정리와 저장소 루트 정돈으로 제한했다.

## 작업 내용

### ProviderRouter 추가
- `api/providers.py`를 추가했다.
- `MockProvider`, `TestProvider`, `BacktestProvider`, `PaperTradingProvider`, `LiveTradingProvider`를 모드별 provider 클래스로 정의했다.
- `ProviderRouter.get(mode)`와 `ProviderRouter.list()`를 통해 모드별 provider 선택을 중앙화했다.
- 각 provider는 현재 단계에서 DB 기반 계좌, 목표 괴리, 자산 배분, Top Movers 조회를 위임한다.
- provider별 실제 외부 API 연결은 다음 단위에서 교체할 수 있도록 API 엔드포인트와 서비스 사이의 경계를 만들었다.

### FastAPI 모드 라우팅 정리
- `/api/modes`, `/api/dashboard/summary`, `/api/accounts`, `/api/targets`, `/api/rebalancing/suggestions`, `/api/rebalancing/run`이 provider를 통해 데이터를 읽도록 변경했다.
- 쓰기 가능 여부 검사를 `ModePolicy` 직접 분기 대신 provider의 `assert_user_write_allowed()`로 통일했다.
- API lifespan에서 과거 1분 yfinance 자동 수집 루프를 제거했다. 데이터 입력은 이후 provider/ingestion 계층에서 명시적으로 연결한다.

### 레거시 코드 삭제
- 과거 경제지표 수집 파이프라인 패키지를 삭제했다.
  - `backend/`
  - `ingestion/`
  - `storage/`
  - `engine/`
  - `agents/`
- 레거시 실행 스크립트를 삭제했다.
  - `scripts/fetch_history.py`
  - `scripts/run.sh`
  - `scripts/start_scheduler.sh`
  - `scripts/stop_scheduler.sh`
  - `scripts/install_launchd.sh`
  - `scripts/uninstall_launchd.sh`
- 임시/수동 KIS 조회·주문 스크립트도 새 provider 구조로 흡수할 예정이므로 제거했다.
  - `scripts/query_kis_balance.py`
  - `scripts/buy_isa_model_portfolio.py`
- 삭제된 레거시 모듈 전용 테스트를 제거했다.
  - collector/database/monitor/telegram/strategy/technical indicator/legacy architecture 관련 테스트

### 문서와 실행 설정 정리
- `README.md`를 현재 구조 기준으로 다시 작성했다.
- `Dockerfile.api`에서 삭제된 `storage/` 복사를 제거하고 `requirements.txt` 기반 설치로 단순화했다.
- `requirements.txt`에서 레거시 수집/분석 파이프라인 의존성을 제거했다.
- `scripts/setup.sh`의 안내 문구를 대시보드 실행 기준으로 수정했다.
- 오래된 개발 계획 PDF/이미지/리서치 파일과 레거시 개발 로그를 삭제했다.
- `docs/DevelopLog/README.md`를 현재 로그 중심으로 정리했다.

### 테스트 추가
- `tests/test_modes.py`에 ProviderRouter 선택 테스트와 read-only 모드 쓰기 차단 테스트를 추가했다.

## 검증 결과

```bash
PYTHONPATH=. .venv/bin/python -m pytest
# 64 passed, 1 warning

cd web && npm run build
# passed
```

추가 확인:
- 현재 문서/코드에서 삭제된 레거시 경로(`backend`, `ingestion`, `storage`, `scripts/run.sh`, `start_scheduler` 등)를 참조하지 않는 것을 `rg`로 확인했다.

Lint:
- `cd web && npm run lint`는 기존 프론트엔드 파일의 React hook/immutability/unused variable 이슈로 실패한다.
- 이번 단위에서 추가한 `api/providers.py`와 provider 라우팅에는 해당 lint 범위가 없다.

## 미작업 내용

- `PaperTradingProvider`가 아직 한국투자증권 모의투자 API를 직접 호출하지 않는다.
- `LiveTradingProvider`는 아직 실제 계좌 조회 전용 provider로 분리 구현되지 않았다.
- `BacktestProvider`와 `backtest_runs` 실행/조회 API는 아직 미구현이다.
- 삭제된 수집 파이프라인을 대체할 새 데이터 입력 계층은 아직 없다.
- 전략 엔진, 리스크 엔진, 주문 후보/수동 승인 엔진은 새 구조로 다시 설계해야 한다.
- 텔레그램 알림은 API의 미읽은 알림 전송 엔드포인트만 남아 있고, `notification_logs` 기반 중복 방지는 아직 연결되지 않았다.
- 프론트엔드 lint 정리는 별도 단위로 처리해야 한다.

## 다음 실행 가이드

1. `PaperTradingProvider`부터 구현한다. 기존 임시 KIS 스크립트의 인증/잔고 조회 로직을 provider 내부 서비스로 재작성하되, 주문 실행은 아직 연결하지 않는다.
2. `LiveTradingProvider`는 조회 전용으로 구현하고, 주문 관련 capability는 계속 비활성화한다.
3. provider별 오류 상태를 API 응답과 계좌 화면에 노출한다.
4. 이후 `BacktestProvider`에서 기간, 초기자본, 리밸런싱 주기를 입력받아 `backtest_runs`에 저장하는 흐름을 만든다.
5. 프론트엔드 lint 오류는 화면별로 작은 단위로 정리한다.
