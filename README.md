# TripleA - 개인 투자 자동화 대시보드

주요 경제지표·포트폴리오를 실시간 모니터링하고, 텔레그램 알림·리밸런싱 제안·매크로 분석을 제공하는 개인 투자 자동화 플랫폼입니다.

## 📋 시스템 개요

| 항목 | 내용 |
|------|------|
| 프론트엔드 | Next.js 15 (App Router, TypeScript, Tailwind CSS v4) — 포트 3000 |
| 백엔드 API | FastAPI (Python) + JWT 인증 — 포트 8000 |
| 데이터베이스 | SQLite (`data/economic_data.db`, WAL 모드) |
| 데이터 수집 | Yahoo Finance, FRED, 한국은행 ECOS, FMP, SEC |
| 자동 수집 | FastAPI 기동 시 1분 주기 백그라운드 루프 (yfinance) |
| 히스토리 수집 | `scripts/fetch_history.py` — 6개월치 일괄 수집 |
| 알림 채널 | 텔레그램 봇 |
| 스케줄러 | APScheduler (파이프라인 08:30 자동 실행) |
| 테스트 | pytest — 148개 통과 |

---

## 🏗️ 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        Next.js (web/)                           │
│  Dashboard · Portfolio · Macro · Alerts · Calendar · Settings   │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP (REST)
┌────────────────────────▼────────────────────────────────────────┐
│                 FastAPI (api/)  :8000                           │
│  /api/dashboard/summary  /api/macro/history/{key}              │
│  /api/indicators/{key}/history  /api/targets  /api/alerts       │
│  Background Task: 1분 주기 yfinance 수집 루프                    │
└────────────────────────┬────────────────────────────────────────┘
                         │ sqlite3
┌────────────────────────▼────────────────────────────────────────┐
│            SQLite  data/economic_data.db                        │
│  indicators · raw_observations · accounts · holdings            │
│  targets · dashboard_alerts · economic_events · documents       │
└────────────────────────┬────────────────────────────────────────┘
                         │ 수집 파이프라인
┌────────────────────────▼────────────────────────────────────────┐
│  ingestion/  ·  backend/  ·  scripts/fetch_history.py          │
│  Yahoo Finance · FRED · ECOS · KOSIS · FMP · SEC · Naver        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 프로젝트 구조

```
TripleA/
├── api/                    # FastAPI 백엔드
│   ├── main.py             #   앱 진입점, 라우터, 1분 수집 루프
│   ├── services.py         #   비즈니스 로직 (지표, KPI, 리밸런싱)
│   ├── models.py           #   Pydantic 스키마
│   └── db.py               #   SQLite 연결, 테이블 초기화
├── web/                    # Next.js 프론트엔드
│   ├── app/                #   App Router 페이지
│   │   ├── page.tsx        #     대시보드 메인
│   │   ├── macro/          #     매크로 지표 + 히스토리 차트
│   │   ├── portfolio/      #     포트폴리오 배분 도넛차트
│   │   ├── targets/        #     목표 비중 설정
│   │   ├── alerts/         #     알림 관리
│   │   ├── calendar/       #     경제 이벤트 캘린더
│   │   ├── documents/      #     자료실 (리포트·메모)
│   │   └── settings/       #     설정
│   └── components/         #   공통 UI 컴포넌트
├── ingestion/              # 데이터 수집기 (IR, 지표, 종목)
├── backend/                # 텔레그램·차트·스케줄러 파이프라인
├── engine/                 # 전략·리스크·실행 엔진
├── storage/                # DB 스키마·유틸
├── scripts/
│   ├── fetch_history.py    #   6개월 히스토리 수집 (Yahoo/FRED/ECOS)
│   ├── start_dashboard.sh  #   대시보드 통합 실행 스크립트
│   ├── run.sh              #   파이프라인 1회 실행
│   └── start_scheduler.sh  #   파이프라인 스케줄러 실행
├── data/
│   └── economic_data.db    # SQLite DB (WAL 모드)
├── config/
│   ├── indicators.yaml     # 수집 지표 설정
│   └── economic_events.yaml
├── API_KEY/                # API 키 파일 (Git 제외)
│   ├── ECOS_API_KEY
│   ├── FRED_API_KEY
│   ├── GEMINI_API_KEY
│   └── TELEGRAM_KEY
├── tests/                  # pytest 테스트 (148개)
├── config.yaml
└── requirements.txt
```

---

## 🚀 실행 방법

### 1. 환경 설정

```bash
cd /Users/bumsangkim/Dev/TripleA

# 가상환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
pip install yfinance          # 실시간 수집 필수
pip install fredapi           # FRED 히스토리 수집 (선택)
```

### 2. API 키 설정

`API_KEY/` 디렉터리의 파일에 키를 입력합니다 (파일당 키 1개, 개행 없이):

| 파일 | 용도 | 발급처 |
|------|------|--------|
| `ECOS_API_KEY` | 한국은행 지표 | https://ecos.bok.or.kr/api/ |
| `FRED_API_KEY` | 미국 경제지표 | https://fred.stlouisfed.org/docs/api/ |
| `TELEGRAM_KEY` | 알림 전송 | @BotFather |
| `GEMINI_API_KEY` | IR 요약 (선택) | https://aistudio.google.com |

### 3. 6개월 히스토리 수집 (최초 1회)

```bash
source .venv/bin/activate
python scripts/fetch_history.py              # Yahoo + FRED + ECOS 전체
python scripts/fetch_history.py --source yahoo --period 1y   # Yahoo만 1년치
```

수집 대상: KOSPI, KOSDAQ, SPY, QQQ, GOLD, WTI, Brent, DXY, US10Y, SMH, SOXX, XLU, MSFT, GOOGL, META, AMZN, NVDA + FRED(CPI, 기준금리, 실업률 등)

### 4. 대시보드 실행

```bash
# FastAPI + Next.js 동시 실행
bash scripts/start_dashboard.sh

# 또는 개별 실행
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000 &
cd web && npm run dev                       # http://localhost:3000
```

FastAPI 기동 시 **1분 주기 수집 루프가 자동으로 시작**됩니다.

### 5. 파이프라인 (텔레그램 알림)

```bash
# 1회 실행
bash scripts/run.sh

# 스케줄러 실행 (매일 08:30 자동)
bash scripts/start_scheduler.sh
```

---

## 📊 주요 기능

### 대시보드 (`/`)
- KPI 바: 총자산, 현금, 오늘 수익, 매크로 점수
- 주요 지표 티커 (KOSPI, KOSDAQ, SPY, QQQ, GOLD, WTI — 실시간 DB값)
- 계좌 요약, 자산 배분, 목표 이탈 현황, 알림

### 매크로 페이지 (`/macro`)
- 36개 지표 카드 (상태 칩: rising/falling/stable/critical)
- 지표 클릭 시 히스토리 라인차트 (7일/1개월/3개월/6개월 범위 선택)

### 목표 관리 (`/targets`)
- 자산 배분 목표 (국내주식, 해외주식, 채권, ETF, 현금 등)
- 투자/수익 목표 (월 투자 목표, 연 수익률 목표)
- 목표 이탈 시 경고/위험 알림 자동 생성

### 리밸런싱 제안
- 현재 보유 vs 목표 비중 비교
- 이탈 규모 기준 매수/매도 제안 (규칙·사유 포함)

### 자료실 (`/documents`)
- 리포트, 투자 아이디어, 메모, 뉴스 요약 CRUD
- 태그 검색, URL 링크 저장

---

## 🔄 1분 자동 수집 상세

FastAPI 앱 기동 시 `asyncio` 백그라운드 태스크로 자동 시작됩니다.

**수집 대상 (매 1분)**:
| 티커 | 지표 키 | 단위 |
|------|---------|------|
| ^KS11 | KOSPI | pt |
| ^KQ11 | KOSDAQ | pt |
| SPY | SPY | USD |
| QQQ | QQQ | USD |
| GC=F | GOLD | USD |
| CL=F | WTI | USD |
| DX-Y.NYB | DXY | pt |
| ^TNX | US10Y | % |
| SMH | SMH | USD |
| SOXX | SOXX | USD |

DB에 `UPSERT` (당일 이미 있으면 업데이트, 없으면 INSERT).

---

## 🗄️ 주요 DB 테이블

| 테이블 | 내용 |
|--------|------|
| `indicators` | 지표명·날짜·값·단위·출처 (UNIQUE: date, indicator) |
| `raw_observations` | 원본 수집 응답 |
| `accounts` | 계좌 정보 (사용자 등록) |
| `holdings` | 보유 종목 (CSV 업로드 또는 API) |
| `targets` | 자산군별 목표 비중·임계값 |
| `dashboard_alerts` | 목표 이탈·시스템 알림 |
| `economic_events` | 경제 캘린더 이벤트 |
| `documents` | 자료실 (리포트·메모) |

---

## 🧪 테스트

```bash
source .venv/bin/activate
python -m pytest -q          # 148개 전체 실행
python -m pytest -q --tb=short   # 실패 시 짧은 트레이스백
```

---

## 🔧 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/dashboard/summary` | 대시보드 전체 요약 |
| GET | `/api/macro/summary` | 매크로 지표 목록 |
| GET | `/api/macro/history/{indicator}?days=30` | 지표 히스토리 |
| GET | `/api/indicators/{key}/history?days=180` | 차트용 히스토리 |
| GET | `/api/accounts` | 계좌 목록 |
| GET | `/api/allocation` | 자산 배분 현황 |
| GET | `/api/targets` | 목표 비중 목록 |
| PUT | `/api/targets` | 목표 비중 수정 |
| GET | `/api/alerts/recent` | 최근 알림 |
| POST | `/api/alerts/generate` | 알림 수동 생성 |
| GET | `/api/system/status` | 시스템 상태 |
| POST | `/api/auth/token` | JWT 로그인 (admin / triplea123) |

---

## ⚠️ 주의사항

1. `API_KEY/` 디렉터리는 `.gitignore`에 포함되어 있습니다. 절대 커밋하지 마세요.
2. `yfinance`는 비공식 API입니다. Yahoo Finance 정책 변경 시 수집이 중단될 수 있습니다.
3. 매매 신호·리밸런싱 제안은 **참고용**이며 실제 투자 결정에 직접 사용하지 마세요.
4. JWT 시크릿(`JWT_SECRET`)은 운영 배포 시 환경변수로 반드시 교체하세요.
5. `accounts`/`holdings` 테이블이 비어 있는 경우 KPI 총자산은 0으로 표시됩니다. CSV 업로드(`/api/accounts/upload-csv`)로 데이터를 입력하세요.


### 🏗️ 아키텍처

```mermaid
