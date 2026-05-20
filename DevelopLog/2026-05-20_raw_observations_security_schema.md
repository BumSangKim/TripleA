# 개발 일지 - 2026-05-20 (4일차)

## 개요
데이터 감사(raw_observations) 인프라 구축, 보안 강화(API 키 마스킹), DB 스키마 확장,
IR 스크래퍼 확장, monitor stale 판정 로직 고도화, 테스트 커버리지 확대.
커밋 없는 작업 수정(워킹 디렉토리 변경분).

---

## 변경 파일 목록

| 파일 | 변경 유형 |
|------|----------|
| `database.py` | 기능 추가 (raw_observations, 마스킹, 스키마 확장) |
| `collector.py` | 기능 추가 (raw 저장, 보안 마스킹, SEC CapEx 폴백) |
| `ir_scraper.py` | 기능 추가 (대상 종목 확장, AI 키워드 카운터) |
| `monitor.py` | 리팩토링 (period_end 기반 stale 판정 고도화) |
| `main.py` | 소규모 수정 |
| `tests/test_database.py` | 테스트 추가 |
| `tests/test_monitor.py` | 테스트 추가 |
| `tests/test_collector.py` | 신규 추가 |
| `tests/test_ir_scraper.py` | 신규 추가 |
| `tests/test_telegram_sender.py` | 신규 추가 |
| `tests/test_config_metadata.py` | 신규 추가 |
| `config/indicators.yaml` | 지표 메타 보완 |
| `config/economic_events.yaml` | 신규 추가 |

---

## 주요 변경 1: 보안 강화 — API 키 마스킹

### 배경
로그 및 raw_observations 저장 시 URL query string에 포함된 API 키가 노출될 위험.

### 구현 (`database.py`)

```python
_SECRET_KEY_RE = re.compile(
    r"^(api[_-]?key|apikey|access[_-]?token|...secret|auth|authorization|key)$",
    re.I,
)

def mask_sensitive_url(url: str) -> str:
    """URL query string 내 API 키성 파라미터를 ***MASKED***로 치환"""

def mask_sensitive_data(data) -> ...:
    """dict/list 재귀 탐색 후 키 이름 기반 민감값 마스킹 (raw 저장 전 적용)"""
```

### 적용 (`collector.py`)
- `_sanitize_error(e)`: 예외 메시지의 URL을 마스킹 후 logger에 출력
- `_masked_url(url, *secrets)`: 시크릿 문자열을 URL에서 직접 치환

---

## 주요 변경 2: 원본 응답 저장 인프라 (raw_observations)

### 배경
수집 이상 발생 시 원인 추적을 위해 각 API 응답 원본을 DB에 저장.

### 구현 (`database.py`)
- `raw_observations` 테이블: `source`, `indicator`, `obs_date`, `raw_json`, `created_at`
- `save_raw_observation(source, raw_data, indicator, obs_date, db_path)` 함수 추가
  - 저장 실패가 수집 실패로 전파되지 않도록 격리 (`try/except`)

### 적용 (`collector.py`)
- `_save_raw(source, raw_data, ...)` — 저장 격리 래퍼
- `fetch_ecos_keystat()`, `fetch_yahoo_quote()` 등 주요 fetch 함수에 raw 저장 추가

---

## 주요 변경 3: DB 스키마 확장

### 신규 테이블 (`database.py`)

#### `ir_keyword_mentions`
IR 파일링에서 AI 병목 키워드 등장 횟수를 저장.
```sql
CREATE TABLE ir_keyword_mentions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    accession      TEXT NOT NULL,
    ticker         TEXT NOT NULL,
    filing_date    TEXT,
    keyword        TEXT NOT NULL,
    mention_count  INTEGER DEFAULT 0,
    created_at     TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(accession, keyword)
)
```

#### `event_releases` 신규 컬럼
```
revised        REAL          -- 수정 발표값
interpretation TEXT          -- hawkish | dovish | neutral
```

#### `collector_runs` 신규 컬럼
```
finished_at    TEXT          -- 수집 종료 시각
```

---

## 주요 변경 4: IR 스크래퍼 확장 (`ir_scraper.py`)

### 대상 종목 추가
| 추가 종목 | 회사명 |
|----------|--------|
| AVGO | Broadcom |
| SMCI | Super Micro Computer |
| DELL | Dell Technologies |

### AI 병목 키워드 확장
기존 키워드 + `"lead time"`, `"allocation"`, `"supply constrained"`, `"tight supply"`, `"HBM3E"`, `"CoWoS"`, `"advanced packaging"` 추가.

### 신규 함수: `count_ai_bottleneck_keywords(text)`
IR 파일링 텍스트에서 AI 병목 관련 키워드 등장 횟수를 딕셔너리로 반환.
```python
{"data center": 12, "gpu": 8, "HBM": 3, "supply constrained": 1, ...}
```

---

## 주요 변경 5: monitor stale 판정 고도화 (`monitor.py`)

### 변경 배경
5/13 개선(collected_at 기준)이 충분하지 않음.
- `collected_at`은 수집 시점이므로 관측값이 실제로 최신인지 판별하기 부족
- 월간/분기 지표는 `date`가 기간 시작일(예: `2026-04-01`)이므로 stale 오판 지속

### 신규 함수들

#### `_tracked_indicators(conn, meta)`
추적 대상 지표 목록 추출 로직을 별도 함수로 분리 (테스트 가능)

#### `_period_end(date_str, frequency)`
관측 기간의 마지막 날로 날짜를 보정:
- `monthly`: 기간 말일 → 예) `2026-04-01` → `2026-04-30`
- `quarterly`: 분기 말일 → 예) `2026-01-01` → `2026-03-31`
- `daily/weekly`: 그대로

이후 stale 판정은 `_period_end` 기준으로 수행 → 월간 발표치가 기간 시작일로 저장되어도 오판 없음.

#### `observation_quality()` (기존 `check_data_quality()` 대체)
- `observed_date` 컬럼 우선 사용, 없으면 `date` 사용
- `collected_at`은 freshness 판정에 사용하지 않음 (수집 시점일 뿐)

---

## 주요 변경 6: FMP CapEx → SEC EDGAR 폴백 (`collector.py`)

FMP 수집 실패 시 SEC EDGAR에서 직접 CapEx를 가져오는 폴백 추가:
```python
def fetch_fmp_capex(ticker, limit=5, db_path=None):
    ...
    if res.status_code in (401, 403):
        _record_auth_error("FMP", ...)
        return fetch_sec_capex(ticker, limit=limit, db_path=db_path)  # ← 폴백
```

---

## 신규 설정 파일

### `config/economic_events.yaml`
경제 이벤트 일정 정의 (CPI, FOMC, NFP 등) — `event_releases` 테이블 시드용.

---

## 테스트

```
59 passed in 1.34s
```

신규 테스트 파일:
- `tests/test_collector.py` — fetch 함수 mock 테스트
- `tests/test_ir_scraper.py` — `count_ai_bottleneck_keywords` 등
- `tests/test_telegram_sender.py` — `send_api_alert`, `send_report` mock
- `tests/test_config_metadata.py` — `indicators.yaml` 스키마 검증

---

## 현재 파이프라인 상태 (2026-05-20 기준)

| 항목 | 상태 |
|------|------|
| 수집 지표 수 | 26개 (CapEx 제외) |
| 완전성 | 100.0% |
| 단위 테스트 | **59/59** 통과 |
| raw_observations | ECOS / Yahoo 원본 저장 |
| IR 대상 종목 | NVDA / MU / TSMC / AMD / INTC / MSFT / AMZN / META / GOOGL / **AVGO / SMCI / DELL** |
| AI 키워드 | HBM3E, CoWoS, advanced packaging 등 확장 |
| 보안 | URL / dict 내 API 키 자동 마스킹 |
