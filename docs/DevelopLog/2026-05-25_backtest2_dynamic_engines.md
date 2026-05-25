# 2026-05-25 Backtest2 Dynamic Engines

## 개발 내용

- `docs/DevelopPlans/back_test2.md` 기준으로 실제 계좌 연동을 제외하고 미완성 항목을 재귀적으로 점검했다.
- `MacroDataService`와 `MacroEngine`을 추가했다.
  - `indicators.date <= as_of_date` 조건으로 과거 시점 스냅샷만 읽는다.
  - VIX, PMI, 장단기 금리차, 실업률 기반으로 `risk_on`, `neutral`, `cautious`, `risk_off`를 판단한다.
  - `TripleAAllocator`가 macro regime에 따라 bucket target을 조정한다.
- `TradeDataService`, `BottleneckDataService`를 추가했다.
  - 수출입/병목 데이터는 `release_date <= as_of_date` 조건을 강제한다.
  - `sector_asset_map` 조회 서비스를 추가했다.
- `BottleneckSectorEngine`과 `SectorTiltEngine`을 추가했다.
  - 수출입 YoY와 상대강도 지표로 섹터 병목 점수를 만든다.
  - `active`, `emerging` 섹터는 위성자산에 제한된 tilt를 적용한다.
  - risk_off 구간에서는 sector tilt를 축소한다.
- 백테스트 상세 API를 추가했다.
  - `GET /api/backtests/runs/{id}/decisions`
  - `GET /api/backtests/runs/{id}/trades`
  - `GET /api/backtests/runs/{id}/positions`
  - `GET /api/strategy/universes`
  - `GET /api/strategy/profiles`
  - `GET /api/strategy/sector-taxonomy`
- `BacktestRunResponse`에 `decisions`를 포함했다.
- `backtest_sector_decisions` 저장을 연결했다.
  - run별 decision과 섹터 점수 상세가 `decision_id`로 연결된다.
- `BacktestEngine` 비용 처리를 보강했다.
  - 수수료, 슬리피지, 세금을 거래 기록에만 남기지 않고 현금에서 차감한다.
  - 현금 자산은 별도 `CASH_BALANCE` 거래로 맞춘다.
- `/backtests` 화면에 decision log를 추가했다.
  - macro regime/score
  - bucket weights
  - final weights
  - bottleneck scores
  - decision reasons

## 검증

- 전체 Python 테스트:
  - `PYTHONPATH=. .venv/bin/python -m pytest tests`
  - 결과: `127 passed`
- 프론트 변경 파일 eslint:
  - `npm exec eslint -- app/backtests/BacktestsPageClient.tsx lib/types.ts`
  - 결과: 통과
- 전체 프론트 lint:
  - `npm --prefix web run lint`
  - 결과: 실패
  - 원인: 기존 `web/components/dashboard/DailyCheckPanel.tsx`의 `react-hooks/set-state-in-effect`

## 커밋

- `0d555e9 feat: add macro regime engine for backtests`
- `c5277b7 feat: add bottleneck sector tilt engine`
- `761e7f9 feat: add backtest decision detail APIs`
- `630e01e fix: deduct backtest trading costs from cash`
- `5eb9d4c feat: show backtest decision logs in UI`
- `8ea15d3 feat: save backtest sector decision details`

## 미작업 내용

- `api/data_collectors/` 구조는 아직 계획대로 분리되지 않았다.
  - 기존 `scripts/collect_historical_data.py`가 있으므로 다음 작업에서 `price_collector.py`, `fx_collector.py`로 옮기거나 감싸야 한다.
- `POST /api/market-data/collect`는 아직 없다.
  - 네트워크 수집과 API 실행 정책을 정한 뒤 추가해야 한다.
- `MacroEngine`은 휴리스틱 초기 버전이다.
  - FRED/ECOS 지표별 release date가 있는 구조로 확장하면 미래 데이터 누수 방지가 더 정밀해진다.
- 수출입/병목 데이터 coverage 검증은 아직 `BacktestEngine` 시작 단계에 연결되지 않았다.
  - 현재는 가격/환율 coverage만 실행을 막는다.
- `backtest_sector_decisions` 조회 API와 UI는 아직 없다.
  - 저장은 연결됐지만 별도 상세 화면은 decision log의 aggregate score 중심이다.
- `SectorTiltEngine`은 같은 bucket 내부에서 donor 자산을 줄이는 초기 구현이다.
  - turnover guard, max position, min trade size는 아직 없다.
- UI는 decision log 단건 조회 중심이다.
  - bucket weight 추이, macro regime timeline, bottleneck score chart는 아직 없다.
- 전체 lint 실패는 기존 `DailyCheckPanel.tsx` 이슈다.
  - 이번 백테스트 변경 파일에서는 재현되지 않는다.
- 실제 계좌 연동은 이번 범위에서 제외했다.

## 다음 실행 제안

1. `POST /api/market-data/collect`와 `api/data_collectors/` 구조를 먼저 정리한다.
2. `validate_backtest_data_coverage()`를 시장/매크로/수출입/병목 coverage까지 확장한다.
3. `backtest_sector_decisions` 조회 API와 UI를 연결한다.
4. `TripleAAllocator`에 turnover guard를 추가한다.
5. `/backtests` 화면에 bucket/macro/bottleneck 추이 차트를 추가한다.
