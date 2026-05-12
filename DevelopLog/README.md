# TripleA - economic_data_pipeline 개발 현황 요약

> 최종 업데이트: 2026-05-13  
> 새 대화에서 이 파일을 먼저 읽으면 현재 개발 상황을 빠르게 파악할 수 있습니다.

---

## 프로젝트 목적

매일 08:30 자동으로:
1. 국내외 경제지표 수집 (ECOS / FRED / Yahoo Finance / NY Fed)
2. Hyperscaler AI CapEx 수집 (FMP API)
3. 미국 빅테크 IR 스크래핑 + Gemini AI 한국어 요약
4. 텔레그램 리포트 자동 전송

---

## 실행 방법

```bash
cd /Users/bumsangkim/Dev/TripleA/economic_data_pipeline
source .venv/bin/activate

# 1회 즉시 실행
bash run.sh

# 스케줄러 시작/중지 (08:00/08:20/08:30 자동)
bash start_scheduler.sh
bash stop_scheduler.sh

# 스케줄러 상태 확인
cat .scheduler.pid | xargs ps -p
```

---

## 핵심 파일

| 파일 | 역할 |
|------|------|
| `main.py` | 파이프라인 진입점 |
| `collector.py` | 데이터 수집 |
| `telegram_sender.py` | 텔레그램 전송 |
| `ir_scraper.py` | SEC EDGAR IR 스크래핑 |
| `gemini_client.py` | Gemini AI 요약 |
| `scheduler.py` | APScheduler 자동 실행 |

---

## 현재 완료된 기능

- [x] ECOS 한국 경제지표 8종 (KeyStatisticList API)
- [x] Yahoo Finance 실시간 가격 7종 (KOSPI/KOSDAQ/금/원유/DXY/US10Y)
- [x] FRED 미국 지표 3종 (US_CPI/FED_RATE/USD_INDEX)
- [x] NY Fed 공급망 압력지수 GSCPI
- [x] FMP Hyperscaler CapEx 4종 (MSFT/GOOGL/META/AMZN, 5분기)
- [x] SEC EDGAR 8-K IR 스크래핑 + Gemini 한국어 요약 (신규 파일링만)
- [x] 텔레그램 통합 메시지 (경제지표 + CapEx 1개 메시지)
- [x] 텔레그램 차트 2개 (지표 추이, CapEx 막대그래프)
- [x] 일별 CSV 원시데이터 첨부
- [x] APScheduler 08:30 자동 실행
- [x] 모든 지표 실제 관측 날짜로 저장

---

## 알려진 제약사항

- ECOS `TIME` 필드 공백: CPI/PPI/환율은 날짜를 수집일(오늘)로 저장
- Gemini `gemini-3.1-flash-lite` 간헐적 503 → 자동 재시도/폴백 처리
- Yahoo Finance 당일 일봉 close=None → `regularMarketPrice` 폴백으로 해결

---

## 개발 로그 파일

| 파일 | 내용 |
|------|------|
| [2026-05-12_initial_pipeline.md](./2026-05-12_initial_pipeline.md) | 파이프라인 최초 구축 (수집 모듈, DB, 텔레그램, 스케줄러) |
| [2026-05-13_ir_scraping_and_bugfix.md](./2026-05-13_ir_scraping_and_bugfix.md) | IR 스크래핑, Gemini 요약, 데이터 품질 수정, 메시지 통합 |
