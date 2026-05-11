# TripleA - 자동화 경제지표 데이터 수집·요약 시스템

매일 **08:30**에 주요 경제지표를 수집·분석하여 **텔레그램**으로 자동 전송하는 파이프라인입니다.

## 📋 시스템 개요

| 항목 | 내용 |
|------|------|
| 전송 시각 | 매일 08:30 (Asia/Seoul) |
| 데이터 소스 | 한국은행 ECOS, KOSIS, KRX, FRED, Naver 뉴스, RSS, KIPRIS |
| 저장소 | SQLite (기본) |
| 스케줄러 | APScheduler |
| 전송 채널 | 텔레그램 봇 |

### 수집 지표

| 지표 | 출처 | 주기 |
|------|------|------|
| 소비자물가지수 (CPI) | 한국은행 ECOS | 월간 |
| 생산자물가지수 (PPI) | 한국은행 ECOS | 월간 |
| 원/달러 환율 | 한국은행 ECOS | 일간 |
| 기준금리 | 한국은행 ECOS | 수시 |
| 두바이유 | 한국은행 ECOS | 일간 |
| 코스피 지수 | KRX 거래소 | 일간(거래일) |
| WTI 국제유가 | FRED | 일간 |
| 금 가격 | FRED | 일간 |
| 미국 CPI | FRED | 월간 |
| 미국 기준금리 | FRED | 월간 |
| 공급망 압력지수 (GSCPI) | FRED | 월간 |
| 실업률 | KOSIS | 월간 |

---

## 🚀 실행 방법

### 1. 사전 준비

#### Python 환경 (3.9 이상 필요)

```bash
# Python 버전 확인
python3 --version

# 프로젝트 디렉토리로 이동
cd economic_data_pipeline

# 가상환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows

# 의존성 설치
pip install -r requirements.txt
```

#### (선택) macOS 한글 폰트는 기본 내장(AppleGothic)이므로 별도 설치 불필요
#### Ubuntu 서버 배포 시 한글 폰트 설치

```bash
sudo apt-get update && sudo apt-get install -y fonts-nanum
fc-cache -fv
```

---

### 2. API 키 설정

`.env.example`을 복사하여 `.env` 파일을 만들고 실제 키를 입력합니다.

```bash
cp .env.example .env
```

`.env` 파일을 열어 다음 항목을 수정하세요:

```dotenv
ECOS_API_KEY=발급받은_ECOS_키
FRED_API_KEY=발급받은_FRED_키
TELEGRAM_BOT_TOKEN=텔레그램_봇_토큰
TELEGRAM_CHAT_ID=수신할_채팅_ID
```

#### 필수 API 키 발급처

| API | 발급 URL | 비고 |
|-----|----------|------|
| 한국은행 ECOS | https://ecos.bok.or.kr/api/ | 회원가입 후 발급 (무료) |
| FRED | https://fred.stlouisfed.org/docs/api/ | 이메일 인증 후 발급 (무료) |
| Naver 뉴스 | https://developers.naver.com | 애플리케이션 등록 필요 (선택) |
| KIPRIS | https://plus.kipris.or.kr | 특허청 회원가입 필요 (선택) |

#### 텔레그램 봇 & 채팅 ID 얻는 방법

```
1. Telegram 앱에서 @BotFather 검색
2. /newbot 명령으로 봇 생성
3. 발급된 토큰을 TELEGRAM_BOT_TOKEN에 입력
4. 봇과 대화 후 https://api.telegram.org/bot<토큰>/getUpdates 에서 chat_id 확인
   또는 @userinfobot 에게 메시지 전송하여 자신의 ID 확인
5. TELEGRAM_CHAT_ID에 입력
```

---

### 3. 즉시 실행 (수동 1회)

```bash
cd economic_data_pipeline
python main.py
```

수집 → DB 저장 → 요약 → 텔레그램 전송이 순서대로 실행됩니다.

---

### 4. 스케줄러 실행 (매일 자동化)

```bash
cd economic_data_pipeline
python scheduler.py
```

스케줄표:

| 시각 | 작업 |
|------|------|
| 08:00 | 데이터 수집 및 DB 저장 |
| 08:20 | 요약 지표 산출 및 차트 생성 |
| 08:30 | 텔레그램 리포트 전송 |

> 스케줄러는 포그라운드에서 계속 실행됩니다. 백그라운드 실행을 원한다면 `nohup` 또는 `systemd`를 사용하세요.

---

### 5. 백그라운드 실행 (서버 배포)

#### nohup 방식 (간단)

```bash
nohup python scheduler.py > scheduler_out.log 2>&1 &
echo $!   # PID 확인
```

종료:

```bash
kill <PID>
```

#### systemd 서비스 등록 (Ubuntu 권장)

`/etc/systemd/system/economic-pipeline.service` 파일 생성:

```ini
[Unit]
Description=Economic Data Pipeline Scheduler
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/TripleA/economic_data_pipeline
ExecStart=/home/ubuntu/TripleA/economic_data_pipeline/.venv/bin/python scheduler.py
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
```

등록 및 시작:

```bash
sudo systemctl daemon-reload
sudo systemctl enable economic-pipeline
sudo systemctl start economic-pipeline
sudo systemctl status economic-pipeline
```

#### launchd 서비스 등록 (macOS 권장)

`~/Library/LaunchAgents/com.economic-pipeline.plist` 파일 생성:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.economic-pipeline</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/bumsangkim/Dev/TripleA/economic_data_pipeline/.venv/bin/python</string>
        <string>/Users/bumsangkim/Dev/TripleA/economic_data_pipeline/scheduler.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/bumsangkim/Dev/TripleA/economic_data_pipeline</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/bumsangkim/Dev/TripleA/economic_data_pipeline/pipeline.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/bumsangkim/Dev/TripleA/economic_data_pipeline/pipeline.log</string>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.economic-pipeline.plist
launchctl start com.economic-pipeline
```

---

## 📁 프로젝트 구조

```
economic_data_pipeline/
├── .env                 # API 키 (Git 제외 - .gitignore에 포함)
├── .env.example         # API 키 템플릿
├── .gitignore
├── requirements.txt
├── config.py            # 환경변수 로드
├── collector.py         # API 수집 모듈 (재시도·타임아웃 포함)
├── database.py          # SQLite CRUD
├── preprocessor.py      # 정제·이상치 처리·통계 산출
├── summarizer.py        # 지표 요약
├── chart_generator.py   # Matplotlib 차트 생성
├── telegram_sender.py   # 텔레그램 전송
├── monitor.py           # 품질 모니터링
├── main.py              # 수동 실행 진입점
├── scheduler.py         # APScheduler 자동 실행
├── economic_data.db     # SQLite DB (자동 생성)
└── pipeline.log         # 실행 로그 (자동 생성)
```

---

## 📊 텔레그램 메시지 예시

```
📊 오늘의 경제지표 요약 (2026년 05월 11일)

• 소비자물가지수: `104.20 %` ▲ +0.30%
• 생산자물가지수: `112.50 %` ▲ +0.50%
• 원/달러 환율: `1,320.50 원` ▲ +0.20%
• 기준금리: `3.50 %` ➡ +0.00%
• 코스피: `2,480.30 pt` ▲ +0.40%
• 실업률: `2.80 %` ▼ -0.10%
• 두바이유: `82.40 USD/bbl` ▼ -0.80%
• WTI 국제유가: `79.50 USD/bbl` ▼ -0.60%
• 금 가격: `2,350.00 USD/oz` ▲ +0.15%
```

이후 차트 이미지(코스피, 환율, CPI, 두바이유, WTI, 금 가격 6개 패널)와 CSV 파일도 함께 전송됩니다.

---

## 🔧 운영 모니터링

### 로그 확인

```bash
tail -f pipeline.log
```

### 수집 현황 조회 (SQLite)

```bash
sqlite3 economic_data.db "SELECT indicator, date, value FROM indicators ORDER BY date DESC LIMIT 20;"
```

### 수집 성공률 조회

```bash
sqlite3 economic_data.db "SELECT status, COUNT(*) FROM collect_log WHERE run_date=date('now') GROUP BY status;"
```

---

## 🛠️ 의존성 패키지

| 패키지 | 용도 |
|--------|------|
| `requests` | HTTP API 호출 |
| `pandas` | 데이터 처리 |
| `numpy` | 수치 연산 |
| `matplotlib` | 차트 생성 |
| `apscheduler` | 스케줄러 |
| `python-dotenv` | 환경변수 관리 |
| `feedparser` | RSS 파싱 |
| `ruptures` | 변화점 탐지 |

---

## ⚠️ 주의사항

1. **`.env` 파일은 절대 Git에 커밋하지 마세요.** `.gitignore`에 이미 포함되어 있습니다.
2. `TELEGRAM_CHAT_ID`는 반드시 설정해야 메시지가 정상 전송됩니다.
3. KRX 데이터는 장 마감(15:30) 이후 제공되므로 08:00 수집 시 전일 데이터가 수집됩니다.
4. FRED 데이터 일부(GSCPI 등)는 월간 업데이트이므로 당월 최신값이 반복 수집됩니다.
5. Naver 뉴스 API는 별도 발급이 필요하며 미설정 시 뉴스 수집을 자동으로 건너뜁니다.

---

## 📈 고도화 제안

- **변화점 탐지**: `ruptures` 라이브러리로 급격한 추세 변화 자동 감지
- **ML 예측**: Prophet 또는 ARIMA로 CPI·환율 단기 예측
- **감성 분석**: KR-FinBERT 한국어 모델로 뉴스 감성 지수 산출
- **대시보드**: Grafana + SQLite 연동 실시간 대시보드
- **Gemini AI 요약**: Gemini API를 활용한 자연어 경제 브리핑 생성
