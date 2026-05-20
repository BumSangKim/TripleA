# 개발 일지 - 2026-05-13 (3일차)

## 개요
API 인증/만료 오류 텔레그램 알림 기능 추가, `collected_at` 마이그레이션 버그 수정,
monitor stale 판정 로직 개선. 3건의 커밋.

---

## 커밋 이력

| 커밋 | 날짜 | 내용 |
|------|------|------|
| `2e9864e` | 2026-05-13 | fix: collected_at 컬럼 마이그레이션 오류 수정 |
| `d0eb1db` | 2026-05-13 | feat: API 인증/만료 오류 텔레그램 알림 기능 추가 |
| `24ca5d3` | 2026-05-13 | fix: monitor stale 판정을 collected_at 기준으로 개선 |

---

## 버그 수정 1: `collected_at` 컬럼 마이그레이션 오류

### 원인
`database.py`의 `_migrate_columns()`에서 컬럼 추가 시 함수형 DEFAULT 구문 사용:
```sql
ALTER TABLE indicators ADD COLUMN collected_at TEXT DEFAULT (datetime('now','localtime'))
```
SQLite의 `ALTER TABLE ADD COLUMN`은 함수형 DEFAULT를 지원하지 않아 조용히 실패.
결과적으로 모든 `upsert_indicator()` 호출에서 "table indicators has no column named collected_at" 오류 발생.

### 수정 (`database.py`)
- `_migrate_columns()`에서 `TEXT DEFAULT (datetime(...))` → `TEXT`로 단순화
- 마이그레이션 성공 후 실제 DB에 컬럼 직접 추가 (일회성)
- `upsert_indicator()` 내부에서 `datetime.now().strftime(...)` 으로 값 채움

---

## 신규 기능: API 인증/만료 오류 텔레그램 알림

### 배경
특정 API 키 만료 시 수집 실패가 로그에만 기록되고 사용자가 인지하지 못하는 문제.

### 구현

#### `collector.py`
- `_api_errors: dict[str, str]` — 모듈 수준 런타임 오류 저장소
- `_record_auth_error(api_name, detail)` — 오류 기록 + ERROR 로그 출력
- `get_api_errors()` — 누적 오류 반환 (main에서 호출)
- `clear_api_errors()` — 파이프라인 시작 시 초기화

각 fetch 함수별 감지 로직 추가:

| 함수 | 감지 조건 |
|------|----------|
| `fetch_ecos_keystat()` | HTTP 401/403, 응답 JSON `RESULT.CODE = "ERROR-*"` |
| `fetch_fred()` | HTTP 400/401/403, 응답 JSON `error_code` 필드 |
| `fetch_fmp_capex()` | HTTP 401/403, 응답 JSON `"Error Message"` / `"message"` 필드 |
| `fetch_naver_news()` | HTTP 401/403, 응답 JSON `errorCode` 필드 |

#### `telegram_sender.py`
- `send_api_alert(errors: dict[str, str])` 추가
  - 오류가 있는 API 한국어 라벨로 표시 (ECOS/FRED/FMP/NAVER/KOSIS)
  - `.env` 업데이트 안내 메시지 포함
  - 중복 방지 없음 — 매 실행마다 오류가 있으면 즉시 전송

#### `main.py`
- `collect_all_indicators()` 시작 시 `clear_api_errors()` 호출
- 수집 완료 후 `get_api_errors()` 확인 → 오류 있으면 `send_api_alert()` 즉시 발송

### 텔레그램 알림 메시지 예시
```
🚨 API 인증 오류 감지 (2026-05-13 22:04)

🔑 한국은행 ECOS
   └ ERROR-300: 인증키 오류

🔑 Naver 뉴스 API
   └ HTTP 401 (errorCode=024)

⚠️ API 키 만료 여부를 확인하고 `.env` 파일을 업데이트하세요.
```

---

## 버그 수정 2: monitor stale 판정 로직

### 원인
FRED는 월별 관측 데이터의 `date`를 기간 시작일(예: `2026-04-01`)로 저장.
4월 CPI를 5월 13일 발표 당일 정상 수집했음에도 `date` 기준으로 42일 경과 → `stale_days: 40` 초과 → stale 오판.

```
DB: US_CPI  date=2026-04-01  collected_at=2026-05-13 22:04:12
                 ↑ 42일 전                ↑ 오늘 수집
```

### 수정 (`monitor.py`)
freshness 체크 SQL을 `date` 기준에서 `COALESCE(date(collected_at), date)` 기준으로 변경.
`collected_at`이 있으면 실제 수집일 기준으로 판정, 없는 레코드는 기존 `date` 기준 유지.

```python
# Before
"SELECT MAX(date) FROM indicators WHERE indicator=? AND date >= ?"

# After
"""SELECT MAX(COALESCE(date(collected_at), date))
   FROM indicators
   WHERE indicator=?
     AND COALESCE(date(collected_at), date) >= ?"""
```

### 결과
- US_CPI, FED_RATE stale 해제
- completeness: 92.3% → **100.0%**, stale 지표: 0개

---

## 테스트 / 검증

```bash
# API 오류 추적 기능 단위 테스트
python3 -c "
from collector import get_api_errors, clear_api_errors, _record_auth_error
clear_api_errors()
_record_auth_error('ECOS', 'ERROR-300: 인증키 오류')
assert 'ECOS' in get_api_errors()
print('OK')
"
# → OK

# monitor stale 판정 결과 확인
python3 -c "
import sys; sys.path.insert(0, '.')
from monitor import check_data_quality
r = check_data_quality()
print('완전성:', r['completeness'], '%')
print('stale:', r['stale_indicators'])
"
# → 완전성: 100.0 %, stale: []
```

---

## 현재 파이프라인 상태 (2026-05-13 기준)

| 항목 | 상태 |
|------|------|
| 수집 지표 수 | 26개 (CapEx 제외) |
| 완전성 | 100.0% |
| stale 지표 | 없음 |
| API 오류 알림 | ECOS / FRED / FMP / NAVER 감지 |
| 텔레그램 전송 | 메시지 + 차트 + CSV + IR 요약 |
| 단위 테스트 | 36/36 통과 |
