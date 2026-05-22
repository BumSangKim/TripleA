# 2026-05-22 KIS Provider 오류 구조화

## 기준 문서

- `docs/DevelopPlans/trading-modes-development-plan.md`
- `docs/DevelopLog/2026-05-22_trading_modes_frontend_lint_cleanup.md`

## 이번 개발 단위

KIS Paper 동기화 실패 원인을 설정 누락, 네트워크 오류, KIS API 오류로 구분하고 프론트엔드 계좌 화면에서 사용자 행동 지침까지 표시하도록 연결했다. 민감정보 노출 방지를 위해 서버 응답에는 원문 앱키, 시크릿, 전체 계좌번호를 담지 않는 공개 메시지만 내려보낸다.

## 작업 내용

### KIS 네트워크 오류 분리
- `api/kis.py`에 `KISNetworkError`를 추가했다.
- OAuth 토큰 발급 및 국내 잔고 조회 요청에서 `requests.RequestException`이 발생하면 네트워크 오류로 변환한다.
- HTTP 오류와 JSON 파싱 오류는 기존 `KISAPIError` 경로를 유지한다.

### Provider sync 오류 응답 구조화
- `POST /api/providers/{mode}/sync-accounts`에서 다음 오류를 구분한다.
  - `KIS_CONFIG_MISSING`: KIS 설정 누락, HTTP 503
  - `KIS_NETWORK_ERROR`: KIS 서버 통신 실패, HTTP 504
  - `KIS_API_ERROR`: KIS API 응답 처리 실패, HTTP 502
- `detail`은 `{code, message, userAction}` 형태로 반환한다.
- 로그에는 내부 예외 원인을 남기되, 클라이언트 응답에는 공개 가능한 메시지만 포함한다.

### 프론트엔드 오류 표시 개선
- `web/lib/api.ts`에 `APIRequestError`를 추가해 FastAPI의 구조화된 `detail`을 파싱한다.
- `web/lib/types.ts`에 `APIErrorDetail` 타입을 추가했다.
- 계좌 화면의 `KIS 동기화 실패` 메시지가 서버의 사용자 행동 지침을 함께 보여주도록 변경했다.

### 테스트 추가
- KIS 네트워크 예외가 `KISNetworkError`로 마스킹되는지 테스트했다.
- Provider sync 설정 오류가 구조화된 응답을 반환하고 raw secret 문구를 노출하지 않는지 테스트했다.

### 레거시 확인
- `backend/`, `ingestion/`, `storage/`, `engine/`, `agents/` 디렉터리는 다시 생성되지 않았다.
- 이번 단위는 레거시 파이프라인 파일을 복구하지 않았다.

## 검증 결과

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_kis_provider.py tests/test_api_endpoints.py
# 40 passed, 1 warning

cd web && npm run lint
# passed

cd web && npm run build
# passed

PYTHONPATH=. .venv/bin/python -m pytest
# 70 passed, 1 warning

git diff --check
# passed
```

## 미작업 내용

- 실제 KIS 모의투자 API 호출은 로컬 환경변수 설정 후 계좌 화면에서 수동 검증이 필요하다.
- KIS 보유상품 자산군 분류 규칙은 아직 단순화되어 있다.
- `LiveTradingProvider`의 실계좌 조회 전용 동기화는 아직 미구현이다.
- Paper 모드 주문 후보 생성, 주문 전 수동 승인, 주문 로그는 아직 구현하지 않았다.

## 다음 실행 가이드

1. KIS 보유상품의 ETF/채권형 ETF/국내주식 분류 규칙을 추가한다.
2. 분류 결과가 `holdings.asset_class`와 `account_snapshots`의 국내주식/ETF/채권 집계에 반영되는지 테스트한다.
3. 이후 `LiveTradingProvider`를 조회 전용으로 연결한다.
