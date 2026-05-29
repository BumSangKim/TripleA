# TripleA

개인 투자 의사결정 자동화 대시보드. 거시경제 분석부터 자산 배분, 백테스트, 주문 후보 생성까지 전 파이프라인을 포함하는 FastAPI 백엔드 + Next.js 프론트엔드 시스템입니다.

---

## 목차

- [프로젝트 개요](#프로젝트-개요)
- [아키텍처](#아키텍처)
- [디렉터리 구조](#디렉터리-구조)
- [실행 방법](#실행-방법)
- [트레이딩 모드](#트레이딩-모드)
- [주요 API](#주요-api)
- [투자 파이프라인](#투자-파이프라인)
- [전략 엔진](#전략-엔진)
- [스코어 파이프라인](#스코어-파이프라인)
- [설정 파일](#설정-파일)
- [테스트](#테스트)
- [외부 연동](#외부-연동)

---

## 프로젝트 개요

TripleA는 다음 5단계 투자 파이프라인을 자동화합니다.

```
데이터 수집 → 거시경제/섹터 스코어링 → 위험예산 제어 → 자산 배분 → 주문 후보 생성
```

- 실제 주문 실행은 **사용자 수동 승인**이 필요합니다 (live 모드에서도 주문 자동 실행 없음)
- mock/test/backtest/paper/live 5개 트레이딩 모드를 지원하며, 모드별로 쓰기 권한과 외부 API 호출이 분리됩니다
- 한국투자증권(KIS) API와 연동하여 실계좌 조회 및 모의투자를 지원합니다
- 텔레그램 봇으로 거시경제 레포트와 알림을 발송합니다

---

## 아키텍처

### 레이어 구조

```
┌─────────────────────────────────────────┐
│             Next.js Frontend            │  web/
│  Dashboard · Accounts · Backtests · ... │
└──────────────────┬──────────────────────┘
                   │ HTTP / REST
┌──────────────────▼──────────────────────┐
│           FastAPI Backend               │  api/
│                                         │
│  ┌──────────────────────────────────┐   │
│  │     api/features/<feature>/      │   │
│  │  router.py → service.py          │   │
│  │  repository.py ← ports.py        │   │
│  │  models.py · schemas.py          │   │
│  └──────────────┬───────────────────┘   │
│                 │                       │
│  ┌──────────────▼───────────────────┐   │
│  │     api/strategy/                │   │
│  │  MacroEngine · SectorEngine      │   │
│  │  RiskBudgetEngine · Allocator    │   │
│  │  ScoreLayer · OrderCandidates    │   │
│  └──────────────┬───────────────────┘   │
│                 │                       │
│  ┌──────────────▼───────────────────┐   │
│  │  api/core/ · api/domain/ · api/db/│  │
│  │  api/brokers/ · api/providers/   │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
                   │
        ┌──────────▼──────────┐
        │    SQLite (data/)   │
        │  KIS API · ECOS     │
        │  FRED · FMP · ...   │
        └─────────────────────┘
```

### 설계 원칙

#### Vertical Slice (수직 슬라이스)
모든 기능은 `api/features/<feature_name>/` 단위로 격리됩니다. Feature 간 직접 import는 금지되며 공유 로직은 `api/domain/` 또는 `api/core/`로 추출합니다.

#### Port/Protocol 패턴
Service는 Repository를 직접 import하지 않고, `typing.Protocol` 기반 Port 인터페이스에만 의존합니다. Repository는 Port의 DB-backed 구현체입니다.

#### Import 레이어 규칙

| 레이어 | 허용 | 금지 |
|--------|------|------|
| `api/domain/` | 순수 Python, Pydantic | FastAPI, sqlite3, HTTP |
| `api/core/` | FastAPI 설정, DomainError 매핑 | feature 직접 import |
| `api/features/*/service.py` | Port Protocol, domain | sqlite3, SQL, HTTPException |
| `api/features/*/repository.py` | sqlite3, domain | FastAPI, router, strategy |
| `api/features/*/router.py` | FastAPI, service | repository, db 직접 import |
| `api/strategy/` | 순수 투자 로직 | FastAPI, HTTPException, features |

#### Error 표준
- `DomainError`는 HTTP status_code를 포함하지 않습니다
- HTTP 매핑은 `api/core/errors.py`에서만 수행합니다
- 에러 응답 형식: `{"error": "<code>", "message": "<str>", "details": <dict|null>}`

---

## 디렉터리 구조

```text
TripleA/
├── api/
│   ├── main.py                    # FastAPI 앱 진입점
│   ├── core/                      # 앱 설정, 미들웨어, 예외 핸들러
│   │   ├── app.py                 # create_app() 팩토리
│   │   ├── config.py              # 환경 설정
│   │   ├── dependencies.py        # lifespan, 공통 의존성
│   │   └── errors.py              # DomainError → HTTP 매핑
│   ├── domain/
│   │   └── exceptions.py          # DomainError 계층
│   ├── features/                  # 기능별 수직 슬라이스
│   │   ├── accounts/              # 계좌 조회 및 스냅샷
│   │   ├── alerts/                # 알림
│   │   ├── auth/                  # 인증
│   │   ├── backtests/             # 백테스트 실행/조회
│   │   ├── calendar/              # 경제 캘린더
│   │   ├── dashboard/             # 대시보드 요약
│   │   ├── data_status/           # 데이터 수집 상태
│   │   ├── documents/             # 문서
│   │   ├── holdings/              # 보유 종목
│   │   ├── intraday/              # 장중 모니터링
│   │   ├── macro/                 # 거시경제 지표
│   │   ├── market_data/           # 시장 데이터 조회
│   │   ├── orders/                # 주문 후보 생성/조회
│   │   ├── rebalancing/           # 리밸런싱 계획/실행
│   │   ├── search/                # 검색
│   │   ├── strategy/              # 전략 메타데이터
│   │   ├── system/                # 시스템 상태
│   │   ├── targets/               # 목표 비중
│   │   └── router_registry.py     # 라우터 통합 등록
│   ├── strategy/                  # 투자 전략 엔진 (순수 로직)
│   │   ├── triplea_allocator.py   # 메인 자산 배분기
│   │   ├── macro_engine.py        # 거시경제 레짐 엔진
│   │   ├── bottleneck_sector_engine.py  # 섹터 병목 스코어링
│   │   ├── risk_budget_engine.py  # 위험예산 엔진
│   │   ├── sector_tilt_engine.py  # 섹터 틸트 엔진
│   │   ├── score_layer.py         # 스코어 레이어
│   │   ├── order_candidates.py    # 주문 후보 생성
│   │   ├── decision_logger.py     # 의사결정 로거
│   │   └── indicator_plugins/     # 지표 플러그인
│   ├── score_pipeline/            # 독립 스코어 파이프라인
│   │   ├── contracts.py           # 파이프라인 계약 (ConservativeAction 등)
│   │   ├── scoring.py             # 스코어 계산
│   │   ├── features.py            # 피처 레지스트리
│   │   ├── engines.py             # 파이프라인 실행 엔진
│   │   ├── parameters.py          # 파라미터 레지스트리
│   │   ├── data_quality.py        # 데이터 품질 검증
│   │   ├── backtest.py            # 백테스트 어댑터
│   │   └── audit.py               # 감사 레이어
│   ├── db/                        # DB 연결, 마이그레이션, 시드
│   │   ├── connection.py          # 연결 팩토리
│   │   ├── initialize.py          # DB 초기화
│   │   ├── migrations/            # 스키마 마이그레이션
│   │   └── seeds/                 # 초기 데이터
│   ├── brokers/
│   │   └── kis/                   # 한국투자증권 클라이언트
│   │       ├── client.py          # API 클라이언트
│   │       ├── config.py          # KIS 설정
│   │       ├── models.py          # KIS 응답 모델
│   │       └── errors.py          # KIS 에러 타입
│   ├── providers/                 # 모드별 DataProvider
│   │   ├── modes.py               # TradingMode, ModePolicy
│   │   ├── router.py              # ProviderRouter
│   │   ├── mock.py                # MockProvider
│   │   ├── paper.py               # PaperTradingProvider
│   │   └── live.py                # LiveTradingProvider
│   ├── data/                      # 데이터 수집/저장 레이어
│   │   ├── repository.py          # 원시 데이터 저장소
│   │   ├── ingestion.py           # 데이터 수집 파이프라인
│   │   ├── backfill.py            # 히스토리 백필
│   │   ├── quality.py             # 데이터 품질 검사
│   │   └── snapshot.py            # 데이터 스냅샷
│   ├── market_data/               # 시장 가격 데이터
│   │   ├── price_provider.py      # 가격 공급자
│   │   └── repository.py          # 가격 저장소
│   ├── optimization/              # 파라미터 최적화
│   │   ├── optimizer.py           # 최적화기
│   │   ├── objective.py           # 목적함수
│   │   ├── robustness_tester.py   # 견고성 테스트
│   │   └── reporting.py           # 최적화 결과 리포트
│   ├── backtest_engine.py         # 백테스트 시뮬레이션 엔진
│   ├── backtest_foundation.py     # 백테스트 기반 구조
│   └── backtest_judgment/         # 백테스트 결과 평가
│       ├── evaluator.py           # 성과 평가기
│       └── realized_regime_labeler.py  # 실현 레짐 레이블러
├── web/                           # Next.js 프론트엔드
│   ├── app/                       # App Router 페이지
│   │   ├── page.tsx               # 메인 대시보드
│   │   ├── accounts/              # 계좌 현황
│   │   ├── backtests/             # 백테스트
│   │   ├── macro/                 # 거시경제
│   │   ├── orders/                # 주문 후보
│   │   ├── portfolio/             # 포트폴리오
│   │   ├── reports/               # 리포트
│   │   ├── targets/               # 목표 비중
│   │   └── settings/              # 설정
│   ├── components/                # 공통 컴포넌트
│   └── lib/                       # 유틸리티
├── config/                        # 전략/유니버스/설정 파일
│   ├── asset_universe.yaml        # 투자 자산 유니버스
│   ├── investment_universe.yaml   # 투자 가능 유니버스
│   ├── strategy_profiles.yaml     # 전략 프로파일 (balanced 등)
│   ├── indicators.yaml            # 거시경제 지표 정의
│   ├── risk_budget.yaml           # 위험예산 설정
│   ├── sector_taxonomy.yaml       # 섹터 분류 체계
│   ├── rebalancing.yaml           # 리밸런싱 정책
│   ├── score_definitions.yaml     # 스코어 정의
│   └── parameters/                # 전략 파라미터 레지스트리
├── tests/                         # 테스트 (100+ 파일)
│   ├── architecture/              # 아키텍처 import 계약 테스트
│   ├── features/                  # feature별 단위 테스트
│   ├── strategy/                  # 전략 엔진 테스트
│   ├── domain/                    # 도메인 규칙 테스트
│   ├── brokers/                   # KIS 클라이언트 테스트
│   └── integration/               # 통합 테스트
├── docs/
│   ├── ARCHITECTURE_CONTRACT.md   # 레이어별 import 계약
│   └── REFACTOR_ARCHITECTURE_DECISIONS.md  # 설계 결정 기록
├── scripts/
│   ├── setup.sh                   # 로컬 환경 초기 설정
│   └── start_dashboard.sh         # 개발 서버 실행
├── data/                          # SQLite DB (Git 제외)
├── config.yaml                    # 앱 전역 설정
├── requirements.txt
├── Dockerfile.api
├── Dockerfile.web
└── docker-compose.yml
```

---

## 실행 방법

### 초기 설정

```bash
cd /path/to/TripleA
bash scripts/setup.sh
```

### 개발 서버 (FastAPI + Next.js 동시 실행)

```bash
bash scripts/start_dashboard.sh
```

### 개별 실행

```bash
# FastAPI 백엔드
source .venv/bin/activate
PYTHONPATH=. uvicorn api.main:app --reload --port 8000

# Next.js 프론트엔드
cd web
npm run dev
```

### Docker

```bash
docker-compose up
```

| 서비스 | 주소 |
|--------|------|
| FastAPI | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Next.js 대시보드 | http://localhost:3000 |

---

## 트레이딩 모드

| 모드 | Provider | DB 쓰기 | 외부 API | 주문 정책 |
|------|----------|---------|----------|----------|
| `mock` | `MockProvider` | 읽기 전용 | ✗ | 비활성 |
| `test` | `TestProvider` | 읽기 전용 | ✗ | 비활성 |
| `backtest` | `BacktestProvider` | 결과 저장 | ✗ | 비활성 |
| `paper` | `PaperTradingProvider` | 사용자 데이터 저장 | ✓ | 모의 주문 |
| `live` | `LiveTradingProvider` | 사용자 데이터 저장 | ✓ | 수동 승인 후 실행 |

> **주의**: `live` 모드에서도 주문은 자동 실행되지 않습니다. 주문 후보 생성 후 사용자가 수동 승인해야 합니다.

---

## 주요 API

### 시스템

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/modes` | 지원 모드와 정책 조회 |
| GET | `/api/system/health` | 시스템 상태 확인 |

### 대시보드

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/dashboard/summary` | 포트폴리오 요약 |

### 계좌

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/accounts` | 계좌 목록 조회 |
| GET | `/api/account-policies` | 계좌 유형별 정책 |
| POST | `/api/providers/paper/sync-accounts` | KIS 모의투자 계좌 동기화 (읽기 전용) |
| POST | `/api/providers/live/sync-accounts` | KIS 실계좌 동기화 (읽기 전용) |
| POST | `/api/accounts/{id}/manual-snapshot` | 수동 계좌 스냅샷 저장 |
| PATCH | `/api/accounts/{id}/rebalancing-inclusion` | 리밸런싱 포함 여부 변경 |

### 리밸런싱

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/rebalancing/run` | 리밸런싱 계획 계산 및 저장 |
| GET | `/api/rebalancing/results` | 리밸런싱 실행 이력 조회 |

### 백테스트

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/backtests/run` | 백테스트 실행 |
| GET | `/api/backtests/runs` | 백테스트 실행 이력 |
| GET | `/api/backtests/runs/{id}` | 백테스트 상세 결과 및 자산곡선 |

### 주문

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/orders/draft` | 리밸런싱 기반 주문 후보 생성 |
| GET | `/api/orders/drafts` | 주문 후보 이력 조회 |
| POST | `/api/orders/execute` | 주문 후보 수동 승인 로그 기록 |

### 전략 / 스코어

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/engine/risk-budget` | 전략 버킷별 위험예산 상태 |
| GET | `/api/strategy/metadata` | 전략 메타데이터 조회 |
| GET | `/api/macro` | 거시경제 지표 현황 |

### 시장 데이터

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/market-data/price` | 자산 가격 조회 |
| GET | `/api/data-status` | 데이터 수집 상태 |

---

## 투자 파이프라인

```
config/indicators.yaml          ← 거시경제 지표 정의
        │
        ▼
api/data/ingestion.py           ← 데이터 수집 (ECOS, FRED, FMP, ...)
        │
        ▼
api/strategy/macro_engine.py    ← 거시 레짐 판단 (distribution 출력)
        │
        ▼
api/strategy/bottleneck_sector_engine.py  ← 섹터 병목 스코어링
        │
        ▼
api/strategy/risk_budget_engine.py        ← 위험예산 검사 및 하드 블록
        │
        ▼
api/strategy/triplea_allocator.py         ← 자산 배분 결정
        │
        ▼
api/strategy/order_candidates.py          ← 주문 후보 생성 (검토 전용)
        │
        ▼
사용자 수동 승인 → 실행
```

---

## 전략 엔진

### TripleAAllocator
`api/strategy/triplea_allocator.py`

- `risk_profile` (balanced, conservative, aggressive), `universe_id`, `strategy_mode` 파라미터로 동작
- 거시 레짐 + 섹터 스코어 + 위험예산을 종합해 자산별 목표 비중 계산
- `allocate(as_of_date)` 메서드로 `AllocationDecision` 반환

### MacroEngine
- 거시경제 지표를 수집해 레짐(expansion/contraction/stagflation 등) 분포를 출력
- 단일 레짐 판단이 아닌 확률 분포로 불확실성 반영

### BottleneckSectorEngine
- 섹터별 병목 지표를 분석해 과열/냉각 구간 스코어 산출
- `config/sector_taxonomy.yaml` 기반 섹터 분류

### RiskBudgetEngine
- 포트폴리오 및 계좌별 위험예산 검사
- 하드 제약 위반 시 `BLOCKED` 액션으로 강제 차단

### Conservative Actions
파이프라인에서 불확실한 경우 다음 보수적 액션을 반환합니다:

| 액션 | 의미 |
|------|------|
| `NO_ACTION` | 아무 행동도 취하지 않음 |
| `HOLD` | 현 포지션 유지 |
| `REVIEW_REQUIRED` | 사용자 검토 필요 |
| `RISK_REDUCE_ONLY` | 위험 축소 방향만 허용 |

---

## 스코어 파이프라인

`api/score_pipeline/` — 전략 엔진과 독립적으로 테스트 가능한 스코어 파이프라인

| 모듈 | 역할 |
|------|------|
| `contracts.py` | ConservativeAction, CandidateAction, ReasonCode 등 계약 정의 |
| `parameters.py` | 버전 관리되는 파라미터 레지스트리 |
| `features.py` | 피처 플러그인 레지스트리 |
| `scoring.py` | EMA 스무딩, 정규화, 신뢰도 가중 스코어 계산 |
| `engines.py` | 파이프라인 실행 오케스트레이터 |
| `data_quality.py` | 입력 데이터 품질 검증 |
| `backtest.py` | 포인트-인-타임 누수 방지 백테스트 어댑터 |
| `audit.py` | 의사결정 감사 로그 |

---

## 설정 파일

| 파일 | 설명 |
|------|------|
| `config.yaml` | 앱 전역 설정 (DB 경로, 실행 모드, 위험 한도) |
| `config/asset_universe.yaml` | 투자 자산 유니버스 정의 |
| `config/investment_universe.yaml` | 유니버스별 자산 목록 |
| `config/strategy_profiles.yaml` | balanced/conservative/aggressive 프로파일 |
| `config/indicators.yaml` | 거시경제 지표 수집 및 정의 |
| `config/risk_budget.yaml` | 위험예산 한도 설정 |
| `config/sector_taxonomy.yaml` | 섹터 분류 체계 |
| `config/rebalancing.yaml` | 리밸런싱 정책 및 임계값 |
| `config/score_definitions.yaml` | 스코어 정의 및 가중치 |
| `config/parameters/` | 전략 파라미터 버전 레지스트리 |

환경 변수는 프로젝트 루트의 `.env` 파일에서 관리합니다:

```env
ECOS_API_KEY=...
FRED_API_KEY=...
FMP_API_KEY=...
KIS_APP_KEY=...
KIS_APP_SECRET=...
KIS_ISDEMO=true
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
GEMINI_API_KEY=...
```

---

## 테스트

```bash
source .venv/bin/activate
PYTHONPATH=. python -m pytest
```

테스트는 100개 이상의 파일로 구성됩니다:

| 영역 | 디렉터리/패턴 |
|------|--------------|
| 아키텍처 계약 | `tests/architecture/` |
| Feature 단위 | `tests/features/` |
| 전략 엔진 | `tests/strategy/`, `test_*_engine.py` |
| 스코어 파이프라인 | `test_phase5_*`, `test_score_pipeline_*` |
| 백테스트 | `test_backtest_*`, `test_phase6_13_*` |
| 도메인 | `tests/domain/` |
| KIS 브로커 | `tests/brokers/` |
| 데이터 파이프라인 | `test_phase3_*`, `test_data_*` |
| 통합 | `tests/integration/` |

프론트엔드 검증:

```bash
cd web
npm run lint
npm run build
```

---

## 외부 연동

| 서비스 | 용도 | 설정 |
|--------|------|------|
| 한국투자증권 (KIS) | 실계좌/모의투자 조회 | `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ISDEMO` |
| ECOS (한국은행) | 국내 거시경제 지표 | `ECOS_API_KEY` |
| FRED | 미국 거시경제 지표 | `FRED_API_KEY` |
| Financial Modeling Prep | 주가/재무 데이터 | `FMP_API_KEY` |
| Google Gemini | AI 분석 보조 | `GEMINI_API_KEY` |
| 텔레그램 | 거시경제 레포트/알림 | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| 네이버 | 검색/뉴스 | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` |
