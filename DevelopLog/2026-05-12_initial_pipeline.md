# 개발 일지 - 2026-05-12 (1일차)

## 개요
TripleA 프로젝트의 `economic_data_pipeline` 모듈 최초 구축.  
매일 08:30 자동으로 경제지표를 수집 → DB 저장 → 텔레그램 전송하는 파이프라인.

---

## 커밋 이력
| 커밋 | 내용 |
|------|------|
| `f866712` | feat: 자동화 경제지표 데이터 수집·요약 파이프라인 구축 |
| `3609950` | fix: ECOS StatisticSearch → KeyStatisticList, Telegram chat_id 자동발견 |
| `191cf78` | feat: 실행 스크립트 추가 및 텔레그램 전송 완전 검증 |
| `93b798b` | feat: GSCPI → PMI_SDT(NY Fed), 매크로 지표 추가, Deep Research 모니터링 프레임워크 반영 |
| `88a9e46` | feat: DXY(ICE) 실제값 별도 추가, DTWEXBGS와 분리 |
| `5f2fe85` | feat: FMP API로 Hyperscaler CapEx(MSFT/GOOGL/META/AMZN) 자동 수집/텔레그램 전송 |

---

## 구축된 모듈 목록

| 파일 | 역할 |
|------|------|
| `config.py` | API 키 로드, Telegram chat_id 자동발견 |
| `collector.py` | ECOS / FRED / Yahoo Finance / FMP / NY Fed 데이터 수집 |
| `database.py` | SQLite CRUD (`indicators`, `collect_log`, `ir_filings` 테이블) |
| `main.py` | 파이프라인 통합 진입점 |
| `summarizer.py` | 요약 지표 산출, QoQ/YoY 변화율 계산 |
| `telegram_sender.py` | 텔레그램 메시지·차트·CSV 전송 |
| `chart_generator.py` | matplotlib 다중 지표 차트, CapEx 막대그래프 |
| `scheduler.py` | APScheduler 기반 08:00/08:20/08:30 자동 실행 |
| `monitor.py` | 수집 실패 알림 |
| `setup.sh` | 최초 환경 설정 (venv, 패키지 설치) |
| `run.sh` | 1회 즉시 실행 |
| `start_scheduler.sh` | 스케줄러 백그라운드 시작 |
| `stop_scheduler.sh` | 스케줄러 중지 |

---

## 수집 지표 목록

### 한국 지표 (ECOS KeyStatisticList)
| 지표 | 내부 키 | 출처 |
|------|---------|------|
| 소비자물가지수 | `CPI` | ECOS |
| 생산자물가지수 | `PPI` | ECOS |
| 원/달러 환율(종가) | `USD_KRW` | ECOS |
| 한국은행 기준금리 | `BASE_RATE` | ECOS |
| 실업률 | `UNEMPLOYMENT` | ECOS |
| 국고채수익률(3년) | `BOND_3Y` | ECOS |
| 경제성장률(실질, 전기대비) | `GDP_GROWTH` | ECOS |
| 소비자심리지수 | `CSI` | ECOS |

### 실시간 가격 (Yahoo Finance)
| 지표 | 심볼 | 내부 키 |
|------|------|---------|
| 코스피 | `^KS11` | `KOSPI` |
| 코스닥 | `^KQ11` | `KOSDAQ` |
| 금 선물 | `GC=F` | `GOLD` |
| 두바이유(Brent) | `BZ=F` | `DUBAI_OIL` |
| WTI 원유 | `CL=F` | `WTI` |
| 미국 10Y 금리 | `^TNX` | `US10Y` |
| ICE 달러인덱스 | `DX-Y.NYB` | `DXY` |

### 미국 지표 (FRED)
| 지표 | 시리즈 ID | 내부 키 |
|------|-----------|---------|
| 미국 소비자물가 | `CPIAUCSL` | `US_CPI` |
| 연방기금금리 | `FEDFUNDS` | `FED_RATE` |
| 달러 무역가중지수 | `DTWEXBGS` | `USD_INDEX` |

### 공급망 압력 (NY Fed GSCPI)
| 지표 | 출처 | 내부 키 |
|------|------|---------|
| 공급망 압력지수 | NY Fed GSCPI (XLS) | `PMI_SDT` |

### Hyperscaler CapEx (FMP)
| 기업 | 내부 키 |
|------|---------|
| Microsoft | `CAPEX_MSFT` |
| Alphabet(Google) | `CAPEX_GOOGL` |
| Meta | `CAPEX_META` |
| Amazon | `CAPEX_AMZN` |

---

## 주요 이슈 및 해결

### 이슈 1: ECOS StatisticSearch API 불안정
- **현상**: `StatisticSearch` 엔드포인트 응답 불안정, 다수 지표 수집 실패
- **해결**: `KeyStatisticList` API로 교체 → 100개 지표 일괄 조회 후 이름으로 필터링
- **효과**: 수집 성공률 100% 달성

### 이슈 2: Telegram chat_id 미설정 문제
- **현상**: `.env`에 `TELEGRAM_CHAT_ID` 없으면 전송 불가
- **해결**: `config.discover_chat_id()` 추가 → 봇에 `/start` 전송 시 `getUpdates`로 자동 탐색
- **효과**: 최초 설정 없이도 자동 연결

### 이슈 3: GSCPI 단종
- **현상**: FRED `GSCPI` 시리즈 서비스 종료
- **해결**: NY Fed 공식 XLS 파일 직접 파싱 (xlrd, OLE2 형식)
- **효과**: 최신 GSCPI 데이터 정상 수집

### 이슈 4: DXY vs DTWEXBGS 혼용
- **현상**: FRED `DTWEXBGS`(달러 무역가중지수)를 DXY로 표기하여 오해 발생
- **해결**: Yahoo Finance `DX-Y.NYB`에서 실제 ICE DXY 별도 수집, 두 지표 모두 표시
- **효과**: 달러 강세 지표 이중 검증 가능

### 이슈 5: FMP API v3 레거시 엔드포인트 deprecated
- **현상**: `/api/v3/cash-flow-statement` 엔드포인트 오류
- **해결**: `/stable/cash-flow-statement` 엔드포인트로 변경
- **효과**: MSFT/GOOGL/META/AMZN 5분기 CapEx 정상 수집

---

## 텔레그램 메시지 구조 (v1)

```
📊 오늘의 경제지표 요약 (2026-05-12)
🇰🇷 한국 지표
  • 코스피: 7,822.24 pt ▲ +X.XX%
  ...
🛢️ 국제 원자재
  ...
🇺🇸 미국 지표
  ...
🔗 공급망 압력 (GSCPI·PMI)
  ...
📡 08:30 모니터링 신호 (Deep Research 프레임워크)
  ...

──────────────────────

🏗️ Hyperscaler AI CapEx 분기 추이 (2026-05-12)
  (Deep Research S1 신호)
  MSFT / GOOGL / META / AMZN 5분기 추이 + QoQ/YoY
```

---

## 검증된 동작 값 (2026-05-12 기준)

| 지표 | 값 | 출처 |
|------|-----|------|
| KOSPI | 7,643.15 pt | Yahoo:^KS11 |
| KOSDAQ | 1,179.29 pt | Yahoo:^KQ11 |
| GOLD | $4,678.70/oz | Yahoo:GC=F |
| WTI | $101.28/bbl | Yahoo:CL=F |
| DXY | 98.35 | Yahoo:DX-Y.NYB |
| US10Y | 4.453% | Yahoo:^TNX |
| USD_KRW | 1,489.9원 | ECOS |
| BASE_RATE | 2.5% | ECOS |
| CPI | 119.37 (2020=100) | ECOS |
| CAPEX_MSFT | $30.88B | FMP (2026-03-31) |
| CAPEX_GOOGL | $35.67B | FMP (2026-03-31) |
| CAPEX_META | $19.00B | FMP (2026-03-31) |
| CAPEX_AMZN | $44.20B | FMP (2026-03-31) |
