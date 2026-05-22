# 2026-05-22 RiskBudget 엔진 연결

## 작업 범위

`trading-modes-development-plan.md`의 엔진 레이어 중 `engine_allocations` 기반 위험예산 계산을 먼저 구현했다. 실전 투자와 모의 투자 주문 항목은 제외했다.

## 작업 내용

- `RiskBudgetItem` API 스키마를 추가했다.
- `get_risk_budget_items` 서비스를 추가했다.
  - `engine_allocations`의 `target_ratio`, `min_ratio`, `max_ratio`를 읽는다.
  - `holdings.strategy_bucket` 또는 자산군 fallback 매핑으로 현재 전략 버킷 비중을 계산한다.
  - `DEFENSIVE_CORE`, `AGGRESSIVE_ALPHA`, `LIQUIDITY`별 `normal/warning/danger`, `HOLD/INCREASE/REDUCE`를 산출한다.
- `GET /api/engine/risk-budget` endpoint를 추가했다.
- 리밸런싱 결과 저장 시 위험예산이 `normal`이 아니면 사유에 위험예산 상태를 덧붙인다.
- 위험예산 서비스/API/리밸런싱 사유 연결 테스트를 추가했다.
- `README.md` 주요 API에 위험예산 endpoint를 추가했다.

## 미작업 내용

- `MasterPortfolioEngine`, `DefensiveCoreEngine`, `AggressiveAlphaEngine`, 계좌별 `AccountEngine`은 아직 별도 클래스로 분리하지 않았다.
- 위험예산 결과는 아직 UI에 표시하지 않는다.
- 위험예산 초과 시 리밸런싱 후보 금액을 자동 제한하지는 않는다. 현재는 사유/진단 연결 단계다.

## 레거시 확인

- 레거시 수집 파이프라인이나 주문 실행 스크립트는 추가하지 않았다.
- 변경 범위는 현행 FastAPI 서비스/API/테스트와 문서로 제한했다.

## 검증

- `PYTHONPATH=. .venv/bin/python -m pytest tests/test_api_engine.py` 통과

## 다음 실행 참고

1. 위험예산 상태를 포트폴리오 또는 목표관리 화면에 표시한다.
2. `MasterPortfolioEngine` 클래스를 추가하고 리밸런싱 결과 생성 책임을 서비스 함수에서 엔진 클래스로 옮긴다.
3. 계좌 유형별 엔진을 추가해 ISA/연금/IRP의 사유와 우선순위를 분리한다.
