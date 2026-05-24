# 2026-05-24 Backtest Dynamic Allocator Contract

## 개발 내용

- 백테스트 요청 계약에서 사용자가 입력하던 목표 비중을 제거했다.
  - `BacktestRunRequest`는 `strategyMode`, `riskProfile`, `universeId`, `baseCurrency`, 비용 bps, `dataLookbackYears`를 받는다.
  - `extra="forbid"`로 `targets`가 들어오면 422가 나도록 고정했다.
- `/backtests` 입력 UI에서 목표 비중 입력을 제거하고 전략 조건, 위험 프로파일, 유니버스, 비용 조건 입력으로 교체했다.
- 동적 백테스트 설정 파일을 추가했다.
  - `config/investment_universe.yaml`
  - `config/strategy_profiles.yaml`
  - `config/sector_taxonomy.yaml`
- 동적 백테스트용 DB 스키마를 추가했다.
  - `data_collection_runs`, `trade_series`, `trade_item_sector_map`
  - `bottleneck_indicators`, `sector_asset_map`
  - `backtest_decisions`, `backtest_sector_decisions`
- `investment_universe.yaml` 기반 자산을 `asset_universe`에 시드하도록 보강했다.
- `TripleAAllocator` 초기 버전을 추가했다.
  - 사용자가 비중을 입력하지 않는다.
  - `riskProfile + universeId`를 기준으로 bucket target을 자산 비중으로 변환한다.
  - 위성 섹터 tilt는 병목 엔진 구현 전까지 0으로 둔다.
- `BacktestEngine`이 정적 `targets` 테이블 대신 allocator decision을 사용하도록 변경했다.
  - 리밸런싱 날짜마다 `AllocationDecision`을 생성한다.
  - decision은 `backtest_decisions`에 저장된다.
- 전체 Python 테스트를 실행했다.
  - `PYTHONPATH=. .venv/bin/python -m pytest tests`
  - 결과: `112 passed`

## 커밋

- `f4503f0 feat: redefine backtest request contract`
- `a8865c4 feat: add strategy universe configuration`
- `18cc08a feat: add dynamic backtest data schema`
- `970ce82 feat: use dynamic allocator for backtests`

## 미작업 내용

- `MacroEngine`은 아직 실제 과거 매크로 데이터로 regime을 판단하지 않는다.
  - 현재 decision은 `macro_regime="neutral"`, `macro_score=50`이다.
- `RiskBudgetEngine`의 min/max 강제 로직은 아직 별도 모듈로 분리되지 않았다.
  - 현재는 profile target을 직접 bucket 비중으로 사용한다.
- `BottleneckSectorEngine`과 `SectorTiltEngine`은 아직 미구현이다.
  - `SMH` 같은 satellite 자산은 현재 기본 배분에서 제외된다.
  - 이후 `release_date <= as_of_date` 조건으로 수출입/병목 데이터를 조회해야 한다.
- `backtest_sector_decisions` 저장은 아직 연결되지 않았다.
- 데이터 수집기는 정식 구조(`api/data_collectors/`, `scripts/collect_backtest_data.py`)로 아직 정리되지 않았다.
  - 기존 작업 중인 `scripts/collect_historical_data.py`가 있으므로 다음 작업에서 병합 여부를 먼저 확인해야 한다.
- API 확장 일부는 작업 트리에 이미 수정 중인 파일이 있다.
  - `api/main.py`, `api/models.py`, `tests/test_api_market_data.py` 상태를 먼저 확인하고 이어가야 한다.
- 프론트 결과 화면은 decision log, bucket weights, sector scores 표시가 아직 없다.
  - `web/app/backtests/BacktestsPageClient.tsx`에도 작업 중인 변경이 있으니 먼저 diff를 확인해야 한다.
- 거래 비용은 현재 trade에 기록되지만 포트폴리오 현금/가치에서 비용 차감까지 완전하게 반영하지 않는다.
  - 다음 BacktestEngine 정교화 단계에서 현금 장부를 분리해야 한다.
- 실제 계좌 연동은 이번 계획 범위에서 제외한다.

## 다음 실행 제안

1. 작업 트리의 기존 미커밋 변경을 먼저 확인한다.
2. `RiskBudgetEngine`을 추가하고 bucket min/max를 강제한다.
3. `MacroEngine`을 추가하되 반드시 `as_of_date` 이후 데이터 사용 금지 테스트를 먼저 둔다.
4. 수출입/병목 조회 서비스와 `BottleneckSectorEngine`을 추가한다.
5. `BacktestEngine`에 현금 장부와 비용 차감을 반영한다.
