# 2026-05-21 대시보드 초기 구현

## 작업 내용

### FastAPI 백엔드 API 서버 (api/)
- `api/__init__.py` — 패키지 초기화
- `api/db.py` — SQLite 연결 헬퍼, 대시보드 전용 테이블 마이그레이션
- `api/models.py` — Pydantic 응답 스키마 (KPISummary, MacroIndicator, TargetItem, …)
- `api/services.py` — 비즈니스 로직 (룰 기반 리밸런싱, 매크로 지표 조회)
- `api/main.py` — FastAPI 앱, CORS, JWT 인증, 전체 REST 엔드포인트

### Next.js 대시보드 (web/)
- **레이아웃**: `Sidebar`, `Header` (티커바, 알림, 프로필)
- **KPI Bar**: 매크로 점수, 총자산, 일간 손익, 목표 달성률, 리스크
- **매크로 패널**: 12개 경제 지표 카드 (미니 스파크라인 포함)
- **계좌 패널**: 도넛 차트 (자산 구성), 계좌 목록
- **목표/괴리 패널**: Progress bar + 색상 경고 (normal/warning/danger)
- **리밸런싱 제안**: 룰 기반 테이블 (비중 축소/확대/관망)
- **Top Movers**: 보유 종목 등락률 순위
- **경제 캘린더**: D-Day 카운트, 중요도 태그
- **알림 패널**: 읽음 처리 지원, 레벨별 색상
- **자료실 패널**: 문서 카테고리 바로가기
- **시스템 상태**: 파이프라인 실행 상태
- **인사이트 패널**: 매크로/포트폴리오/리스크/권장 대응

### 설치 패키지
- Python: `fastapi`, `uvicorn[standard]`, `python-jose[cryptography]`, `passlib[bcrypt]`, `python-multipart`
- Node: Next.js 16, TypeScript, Tailwind CSS

## 실행 방법

```bash
# 터미널 1 - FastAPI 백엔드
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000

# 터미널 2 - Next.js 프론트엔드
cd web && npm run dev

# 또는 한 번에
./scripts/start_dashboard.sh
```

## 접속 URL
- 대시보드: http://localhost:3000
- API 문서(Swagger): http://localhost:8000/docs
- API Health: http://localhost:8000/api/health

## 데이터 흐름
1. 기존 파이프라인 → `data/economic_data.db` 수집
2. FastAPI → DB에서 읽어 REST API 제공
3. Next.js → API 호출 → 대시보드 렌더링 (5분마다 자동 갱신)
4. DB 없을 경우 → 프론트엔드 mock 데이터로 폴백

## 다음 단계 (Week 2~)
- [ ] 실제 holdings 테이블 연동 (현재 mock 비중 사용 중)
- [ ] 계좌 CSV 업로드 엔드포인트 구현
- [ ] 경제 캘린더 이벤트 DB 데이터 연동
- [ ] 매크로 미니 차트 히스토리 데이터 연동
- [ ] JWT 인증 미들웨어 적용 (현재 공개 API)
