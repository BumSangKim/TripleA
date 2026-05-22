# 2026-05-22 KIS Paper Provider 읽기 전용 동기화

## 기준 문서

- `docs/DevelopPlans/trading-modes-development-plan.md`

## 이번 개발 단위

직전 단위에서 만든 `ProviderRouter`에 한국투자증권 모의투자 계좌 조회를 읽기 전용으로 연결했다. 주문 실행은 포함하지 않고, OAuth 토큰 발급, 국내주식 잔고 조회, 계좌/보유종목/스냅샷 저장까지를 한 번에 검증 가능한 범위로 제한했다.

## 작업 내용

### KIS 읽기 전용 클라이언트 추가
- `api/kis.py`를 추가했다.
- `.env` 또는 환경변수에서 KIS 앱키, 시크릿, 계좌번호를 읽어 `KISConfig`로 정규화한다.
- `paper` 모드는 `force_demo=True`로 동작해 모의투자 base URL과 demo credential을 우선 사용한다.
- 계좌번호는 `KIS_CANO`/`KIS_ACNT_PRDT_CD` 또는 `KIS_ACCOUNT_NO=12345678-01` 형식을 모두 지원한다.
- 계좌번호 표시에는 `mask_account()`를 사용해 전체 계좌번호를 노출하지 않는다.
- 국내주식 잔고 응답을 `KISBalanceSnapshot`, `KISPosition`으로 정규화한다.

### PaperTradingProvider 동기화 연결
- `PaperTradingProvider.sync_accounts()`를 구현했다.
- KIS 모의투자 잔고를 조회한 뒤 `accounts`, `holdings`, `account_snapshots`에 저장한다.
- 저장된 계좌는 `broker='KIS'`, `data_source='KIS_PAPER'`, `connection_status='CONNECTED'`, `trade_status='PAPER_READ_ONLY'`로 표시한다.
- 기존 KIS paper 계좌가 있으면 새 계좌를 만들지 않고 같은 계좌를 업데이트한다.
- 보유종목은 동기화 시점의 broker 조회 결과와 맞추기 위해 해당 계좌의 기존 holdings를 교체한다.

### API 엔드포인트 추가
- `POST /api/providers/{mode}/sync-accounts`를 추가했다.
- `paper` 모드에서는 KIS 모의투자 동기화를 수행한다.
- 아직 구현되지 않은 provider는 `501`을 반환한다.
- KIS 설정 누락은 `503`, KIS API 오류는 `502`로 반환한다.

### 설정/문서
- `.env.example`에 `KIS_ACCOUNT_TYPE`, `KIS_ACCOUNT_NAME`을 추가했다.
- `README.md`의 주요 API 표에 paper provider sync 엔드포인트를 추가했다.

### 테스트 추가
- `tests/test_kis_provider.py`를 추가했다.
- demo credential 우선순위, 계좌번호 파싱, 잔고 응답 정규화, provider DB 저장을 테스트한다.
- `tests/test_api_endpoints.py`에 미구현 provider sync의 `501` 응답 테스트를 추가했다.

## 검증 결과

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_kis_provider.py tests/test_modes.py tests/test_api_endpoints.py
# 45 passed, 1 warning

PYTHONPATH=. .venv/bin/python -m pytest
# 68 passed, 1 warning

cd web && npm run build
# passed

git diff --check
# passed
```

레거시 확인:
- `backend/`, `ingestion/`, `storage/`, `engine/`, 구 실행 스크립트 디렉터리는 다시 생성되지 않았다.
- 검색 결과에 남은 레거시 경로 문자열은 이전 개발 로그의 삭제 내역 설명뿐이다.

## 미작업 내용

- 실제 KIS API 호출은 로컬 환경변수 설정 후 수동 실행 검증이 필요하다.
- `LiveTradingProvider`의 실계좌 조회 전용 동기화는 아직 미구현이다.
- Paper provider 동기화 버튼은 프론트엔드 계좌 화면에 아직 연결하지 않았다.
- KIS 응답의 상품 유형별 자산군 분류는 현재 `국내주식` 기본값이며, ETF/채권형 ETF 분류 로직은 후속 작업이 필요하다.
- provider별 오류 상태를 계좌 화면에 표시하는 UI는 아직 없다.
- 주문 후보 생성, 주문 전 수동 승인, 주문 로그는 아직 구현하지 않았다.
- 프론트엔드 lint 오류 정리는 여전히 별도 단위로 남아 있다.

## 다음 실행 가이드

1. 계좌 화면에 `paper` 모드일 때 `KIS 동기화` 버튼을 추가하고 `POST /api/providers/paper/sync-accounts`를 연결한다.
2. 동기화 성공 후 계좌 목록, 스냅샷, 리밸런싱 로그를 재조회하도록 한다.
3. KIS 동기화 실패 메시지를 사용자에게 표시하되, 앱키/시크릿/전체 계좌번호는 절대 출력하지 않는다.
4. 이후 `LiveTradingProvider`는 조회 전용으로만 구현하고 `trade_status`를 명확히 `LIVE_READ_ONLY`로 둔다.
