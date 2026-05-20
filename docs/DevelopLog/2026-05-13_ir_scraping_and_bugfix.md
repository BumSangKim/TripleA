# 개발 일지 - 2026-05-13 (2일차)

## 개요
IR 스크래핑 + Gemini AI 요약 기능 추가, 데이터 품질 수정, 메시지 구조 개선.

---

## 커밋 이력

| 커밋 | 날짜 | 내용 |
|------|------|------|
| `6a3af6f` | 2026-05-13 | feat: SEC EDGAR 8-K IR 스크래핑 + Gemini AI 한국어 요약 자동화 |
| `24d91d9` | 2026-05-13 | fix: 실시간 가격 지표 Yahoo Finance로 교체, 실제 데이터 날짜 저장 |
| `1e1f556` | 2026-05-13 | fix: Yahoo Finance 최신 데이터 수집 로직 개선 (KOSPI/KOSDAQ 날짜 stuck 해결) |

---

## 신규 기능 1: SEC EDGAR IR 스크래핑 + Gemini 요약

### 구현 내용 (`ir_scraper.py`, `gemini_client.py`)

**`ir_scraper.py`**
- `COMPANY_CIKS`: MSFT/AMZN/META/GOOGL의 SEC CIK 번호 딕셔너리
- `fetch_recent_8k(ticker, limit=5)`: SEC EDGAR API에서 최근 8-K 파일링 목록 조회
- `fetch_filing_text(accession, cik, primary_doc)`: 파일링 인덱스에서 **Exhibit 99.1 자동 탐지**, BeautifulSoup HTML 파싱, 8,000자 제한
- `get_new_filings(db_path)`: `ir_filings` DB의 기존 accession과 비교 → **미등록 건만 반환** (중복 방지)

**`gemini_client.py`**
- 모델 우선순위: `gemini-3.1-flash-lite` → `gemini-2.5-flash` → `gemini-2.5-flash-lite`
- `gemini-3.1-flash-lite`: 무료 티어 사용 가능 (입력/출력 모두 무료) ✅
- `gemini-2.0-flash`: 무료 한도 0 (429 즉시) ❌
- 503 자동 재시도 (10s, 20s 대기), 429 다음 모델로 폴백
- 요약 형식 (한국어 5개 항목):
  1. 핵심 실적 (매출/순이익)
  2. 클라우드·AI 비즈니스 현황
  3. CapEx 투자 계획
  4. 향후 가이던스
  5. 리스크 요인

**`database.py` 추가**
- `ir_filings` 테이블: `(accession UNIQUE, ticker, company, date, form, summary, seen_at)`
- `is_filing_seen(accession)`, `save_ir_filing(filing, summary)` 추가

**`telegram_sender.py` 추가**
- `send_ir_summaries(filings_with_summaries)`: IR 요약 개별 메시지 전송
- 4096자 제한 처리, MarkdownV2 이스케이프

**`main.py` IR 플로우**
```python
new_filings = get_new_filings(db_path=DB_PATH)
if not new_filings:
    logger.info("[IR] 신규 파일링 없음 - IR 요약 건너뜀")
else:
    # fetch_filing_text → summarize_ir → save_ir_filing → send_ir_summaries
```
→ **신규 파일링이 있을 때만** Gemini 요약 + 텔레그램 전송

### SEC CIK 번호
| 기업 | CIK |
|------|-----|
| Microsoft | `0000789019` |
| Amazon | `0001018724` |
| Meta | `0001326801` |
| Alphabet(Google) | `0001652044` |

### 초기 시드
- 최초 실행 시 4개사 × 5건 = 20건 ir_filings에 저장 → 이후 신규 파일링만 처리

---

## 데이터 품질 수정: Yahoo Finance → 실제 날짜 저장

### 문제 1: ECOS TIME 필드 공백
- **현상**: ECOS `KeyStatisticList`의 `TIME` 필드가 빈 문자열로 반환
- **해결**: KOSPI/KOSDAQ/금/원유를 Yahoo Finance로 교체 → 실제 거래 날짜 사용
- **저장 방식**: `safe_store(indicator, value, source, unit, date_str=actual_date)`

### 문제 2: FRED 날짜 오염
- **현상**: 수집일(오늘)을 날짜로 저장하여 실제 관측 날짜와 불일치
- **해결**: `_fred_date_val(obs)` 함수 추가 → FRED 응답의 `date` 필드 직접 사용

### 문제 3: WTI/US10Y 날짜 선택
- **로직**: Yahoo Finance와 FRED 중 더 최신 날짜의 값 우선 사용
```python
if yahoo_wti and yahoo_wti[0] >= fred_wti[0]:
    safe_store("WTI", yahoo_wti[1], "Yahoo:CL=F", ...)
```

---

## 데이터 품질 수정: Yahoo Finance KOSPI/KOSDAQ 날짜 stuck

### 문제
- **현상**: `run.sh` 실행 시 KOSPI/KOSDAQ이 전날 날짜(2026-05-11)에 고착
- **원인**: Yahoo Finance `5d, 1d` 일봉 데이터에서 당일 candle의 `close=None` 반환
  - Yahoo는 장 마감 후 일정 시간이 지나야 `close` 값을 확정
  - 기존 코드는 `None`을 건너뛰고 전날 close 반환

### 해결 (`collector.py - fetch_yahoo_quote()`)
```python
# 방법 1: 완전한 일봉 close 데이터 (None이 아닌 가장 최신값)
# 방법 2: meta.regularMarketPrice + 거래소 타임존 기반 날짜 (항상 최신)
# → comparator: regularMarketPrice 날짜 > 일봉 날짜 → regularMarketPrice 사용
```
- `exchangeTimezoneName` 활용 (e.g., `Asia/Seoul`, `America/New_York`)
- `datetime.fromtimestamp(rm_time, tz=UTC).astimezone(exchange_tz)` → 정확한 현지 날짜

### 결과
| 지표 | 수정 전 | 수정 후 |
|------|---------|---------|
| KOSPI | 2026-05-11 (7822) | **2026-05-12 (7643.15)** |
| KOSDAQ | 2026-05-11 (1207) | **2026-05-12 (1179.29)** |

---

## 텔레그램 메시지 구조 개선 (v2)

### 변경 전 (v1)
- 메시지 1: 경제지표 요약 텍스트
- 메시지 2: 주요 지표 차트
- 메시지 3: CapEx 분기 추이 텍스트
- 메시지 4: CapEx 차트

### 변경 후 (v2)
- **메시지 1**: 경제지표 요약 + CapEx 분기 추이 **통합** (구분선으로 구분)
- 메시지 2: 주요 지표 차트 (이미지)
- 메시지 3: CapEx 분기 추이 차트 (이미지)

합산 메시지 길이: 약 1,772자 (텔레그램 4,096자 제한 내 충분한 여유)

---

## 스케줄러 상태 확인

- `start_scheduler.sh` 실행 → PID `67843` 정상 동작 중
- `scheduler.py` 구조:
  - 08:00 `job_collect()`: 데이터 수집 및 DB 저장
  - 08:20 `job_summarize()`: 요약 연산 및 차트 생성 (사전 검증)
  - 08:30 `job_send()`: 텔레그램 전송
- 타임존: `Asia/Seoul`
- 중복 실행 방지: `.scheduler.pid` 파일로 프로세스 관리

---

## CPI 데이터 단위 수정

- **현상**: DB에 CPI/PPI 단위가 `%`로 잘못 저장된 기존 데이터 4건 발견
- **원인**: 이전 버전 코드에서 `ECOS_KEY_MAP`의 단위 선언 오류
- **해결**: 직접 SQL UPDATE로 `%` → `index` 수정
- **현재 코드**: `main.py`의 `ECOS_KEY_MAP`에 `"index"`로 정상 선언

---

## 현재 파일 구조

```
economic_data_pipeline/
├── .env                    # API 키 (git 제외)
├── .env.example            # API 키 예시 (git 포함)
├── .venv/                  # Python 가상환경
├── config.py               # 설정 및 Telegram chat_id 자동발견
├── collector.py            # 데이터 수집 (ECOS/FRED/Yahoo/FMP/NY Fed)
├── database.py             # SQLite CRUD
├── main.py                 # 파이프라인 진입점
├── summarizer.py           # 지표 요약 (QoQ/YoY)
├── telegram_sender.py      # 텔레그램 전송
├── chart_generator.py      # matplotlib 차트 생성
├── scheduler.py            # APScheduler 08:00/08:20/08:30
├── monitor.py              # 수집 실패 알림
├── ir_scraper.py           # SEC EDGAR 8-K 스크래핑
├── gemini_client.py        # Gemini AI 요약
├── preprocessor.py         # 데이터 전처리 유틸
├── economic_data.db        # SQLite DB (git 제외)
├── pipeline.log            # 실행 로그 (git 제외)
├── setup.sh                # 초기 환경 설정
├── run.sh                  # 1회 즉시 실행
├── start_scheduler.sh      # 스케줄러 시작
└── stop_scheduler.sh       # 스케줄러 중지
```

---

## 환경 정보

| 항목 | 값 |
|------|-----|
| Python | 3.14.2 |
| venv 경로 | `economic_data_pipeline/.venv/` |
| DB | `economic_data.db` (SQLite) |
| 로그 | `pipeline.log` |

## API 키 목록

| 서비스 | 환경변수 | 비고 |
|--------|----------|------|
| 한국은행 ECOS | `ECOS_API_KEY` | KeyStatisticList |
| FRED (연준) | `FRED_API_KEY` | 미국 경제지표 |
| Telegram Bot | `TELEGRAM_BOT_TOKEN` | `@bum_triple_a_bot` |
| Telegram Chat | `TELEGRAM_CHAT_ID` | `8489492474` (자동발견 가능) |
| FMP | `FMP_API_KEY` | CapEx 수집 |
| Gemini | `GEMINI_API_KEY` | IR 요약 (gemini-3.1-flash-lite) |

## GitHub

- Repository: `https://github.com/BumSangKim/TripleA.git`
- Branch: `main`
- 최신 커밋: `1e1f556` (2026-05-13)
- **주의**: `API_KEY/`, `.env`, `economic_data.db`, `pipeline.log`는 `.gitignore`로 제외
