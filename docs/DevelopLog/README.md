# TripleA 개발 로그 안내

> 최종 업데이트: 2026-05-22

이 디렉터리는 실행 단위별 개발 기록을 보관합니다. 과거 경제지표 수집 파이프라인 로그는 히스토리 참고용이며, 현재 코드베이스의 실행 구조는 `api/`와 `web/` 중심입니다.

## 현재 실행 구조

```bash
cd /Users/bumsangkim/Dev/TripleA
bash scripts/start_dashboard.sh
```

- FastAPI: `api.main:app`
- Frontend: `web/`
- DB: `data/economic_data.db`
- 모드 정책: `api/modes.py`
- Provider 라우팅: `api/providers.py`

## 최신 로그

| 파일 | 내용 |
|------|------|
| `2026-05-22_trading_modes_backtest_ui.md` | 백테스트 화면/API 연결 및 결과 차트 |
| `2026-05-22_trading_modes_backtest_api.md` | 백테스트 실행 API 및 결과 시계열 저장 |
| `2026-05-22_trading_modes_order_history.md` | 주문 draft 이력 조회 API/UI |
| `2026-05-22_trading_modes_order_draft_ui.md` | 주문 후보 생성 및 Paper 승인 로그 UI 연결 |
| `2026-05-22_trading_modes_order_draft_api.md` | 주문 후보 생성 및 Paper 수동 승인 로그 API |
| `2026-05-22_trading_modes_live_read_only_sync.md` | Live provider KIS 실계좌 조회 전용 동기화 |
| `2026-05-22_trading_modes_kis_asset_classification.md` | KIS 보유상품 ETF/채권/국내주식 분류 및 스냅샷 bucket 저장 |
| `2026-05-22_trading_modes_kis_error_details.md` | KIS provider sync 오류 구조화 및 프론트 메시지 개선 |
| `2026-05-22_trading_modes_frontend_lint_cleanup.md` | 프론트엔드 lint/build 품질 게이트 복구 |
| `2026-05-22_trading_modes_kis_sync_ui.md` | 계좌 화면 KIS Paper 동기화 버튼/API 연결 |
| `2026-05-22_trading_modes_kis_paper_provider.md` | KIS 모의투자 Paper provider 읽기 전용 동기화 |
| `2026-05-22_trading_modes_provider_legacy_cleanup.md` | ProviderRouter 도입, 레거시 코드 삭제 |
| `2026-05-22_trading_modes_accounts_ui.md` | 계좌 화면 모드/정책/스냅샷/리밸런싱 로그 연결 |
| `2026-05-22_trading_modes_account_snapshot_rebalance.md` | 계좌 정책/스냅샷/리밸런싱 결과 API 구현 |
| `2026-05-21_dashboard_initial_implementation.md` | 대시보드 초기 구현 |

## 다음 대화에서 먼저 볼 파일

1. `docs/DevelopPlans/trading-modes-development-plan.md`
2. 최신 `docs/DevelopLog/2026-05-22_*`
3. `README.md`
