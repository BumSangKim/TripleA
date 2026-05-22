# TripleA

TripleA는 모의데이터, 백테스트, 모의투자, 실전 조회 모드를 구분해 운용하는 개인 투자 의사결정 대시보드입니다. 현재 저장소는 FastAPI 백엔드와 Next.js 프론트엔드 중심으로 정리되어 있으며, 과거 경제지표 수집 파이프라인 레거시 코드는 제거되었습니다.

## 현재 구조

```text
TripleA/
├── api/                    # FastAPI 백엔드
│   ├── main.py             # API 엔드포인트
│   ├── db.py               # SQLite 스키마와 마이그레이션
│   ├── models.py           # Pydantic 응답/요청 모델
│   ├── modes.py            # mock/test/backtest/paper/live 정책
│   ├── providers.py        # 모드별 DataProvider 라우터
│   └── services.py         # 대시보드/계좌/리밸런싱 서비스
├── web/                    # Next.js 프론트엔드
├── config/                 # indicators/economic events 설정
├── docs/                   # 개발 계획과 개발 로그
├── scripts/
│   ├── setup.sh            # 로컬 환경 초기 설정
│   └── start_dashboard.sh  # FastAPI + Next.js 개발 서버 실행
├── data/                   # 런타임 SQLite DB와 로그, Git 제외
├── tests/                  # 현행 API/모드/설정 테스트
├── Dockerfile.api
├── Dockerfile.web
├── docker-compose.yml
└── requirements.txt
```

## 실행

```bash
cd /Users/bumsangkim/Dev/TripleA
bash scripts/setup.sh
bash scripts/start_dashboard.sh
```

개별 실행:

```bash
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000

cd web
npm run dev
```

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- 대시보드: http://localhost:3000

## 트레이딩 모드

| 모드 | Provider | 쓰기 | 주문 |
|------|----------|------|------|
| `mock` | `MockProvider` | 차단 | 차단 |
| `test` | `TestProvider` | 차단 | 차단 |
| `backtest` | `BacktestProvider` | 결과 저장 | 차단 |
| `paper` | `PaperTradingProvider` | 사용자 데이터 저장 | 모의주문 대상 |
| `live` | `LiveTradingProvider` | 사용자 데이터 저장 | 수동 승인 전 조회 전용 |

## 주요 API

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/modes` | 지원 모드와 정책 조회 |
| GET | `/api/dashboard/summary?mode=paper` | 대시보드 요약 |
| GET | `/api/account-policies` | 계좌 유형별 정책 |
| POST | `/api/providers/paper/sync-accounts` | KIS 모의투자 계좌 읽기 전용 동기화 |
| POST | `/api/providers/live/sync-accounts` | KIS 실계좌 조회 전용 동기화 |
| POST | `/api/accounts/{id}/manual-snapshot?mode=paper` | 수동 계좌 스냅샷 저장 |
| PATCH | `/api/accounts/{id}/rebalancing-inclusion?mode=paper&include=false` | 리밸런싱 포함 여부 변경 |
| POST | `/api/rebalancing/run?mode=paper` | 리밸런싱 결과 계산/저장 |
| GET | `/api/rebalancing/results?mode=paper` | 리밸런싱 실행 로그 |
| POST | `/api/orders/draft` | 리밸런싱 기반 주문 후보 생성 |
| POST | `/api/orders/execute` | Paper 주문 후보 수동 승인 로그 기록 |

## 검증

```bash
source .venv/bin/activate
PYTHONPATH=. python -m pytest

cd web
npm run build
```

`npm run lint`는 일부 기존 프론트엔드 화면의 hook/immutability 정리 작업이 남아 있어 별도 단위로 처리합니다.

## 다음 개발 방향

1. `ProviderRouter`의 provider별 실제 데이터 연결
2. Paper provider의 한국투자증권 모의투자 조회 연동
3. Backtest provider와 `backtest_runs` 저장/조회 흐름 구현
4. Live provider는 조회 전용을 유지하고, 주문은 후보 생성과 수동 승인으로 분리
5. 텔레그램 알림 채널과 `notification_logs` 중복 방지 정책 연결
