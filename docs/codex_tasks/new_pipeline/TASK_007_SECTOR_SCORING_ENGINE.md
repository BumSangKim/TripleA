# TripleA New Pipeline Architecture — Codex Task

## 공통 절대 원칙

이 태스크 팩은 **Legacy 호환 마이그레이션이 아니라 신규 Pipeline Architecture 구현 지시서**다.

Codex는 모든 태스크에서 다음을 준수해야 한다.

```text
No Threshold Switch.
Use Score Flow.
Hard Constraints First.
Backtest Before Execution.
Explain Every Decision.
Use Conservative Fallback on Uncertainty or Error.
Do Not Default to Automatic Execution.
```

금지 사항:

```text
LegacyReferenceEngine 생성 금지
LegacyBridge 생성 금지
Legacy Golden Master / Shadow Compare 구현 금지
기존 TripleAAllocator / MacroEngine / RiskBudgetEngine 투자 판단 로직의 무비판적 이식 금지
Raw Data → Buy/Sell 직결 금지
Single Indicator → Regime Switch 금지
Dominant Regime Label → Fixed Weights 금지
자동 주문 실행 기본값 금지
전략 파라미터 하드코딩 금지
```

허용되는 재사용:

```text
DB 유틸
KIS API read-only client
데이터 수집기
설정 로더
공통 테스트/로깅/타입 유틸
문서화/리포팅 유틸
```

단, 재사용 인프라가 기존 투자 판단 로직을 우회적으로 끌고 오면 안 된다.

## 공통 작업 루프

각 태스크는 반드시 아래 루프를 따른다.

```text
Inspect
→ Implement only this task
→ Add/update tests
→ Run tests
→ If fail, fix and rerun
→ Repeat until pass
→ Update docs/status
→ Move to next task
```

실패한 테스트를 무시하지 않는다. 관련 없는 기존 실패가 있으면 명령, 실패 요약, 관련 없음의 근거, 영향 범위를 기록한다.

# TASK 007 — Sector Scoring Engine

## 목적

sector/asset attractiveness score를 decomposable하고 explainable한 구조로 구현한다.

## 필수 component score

가용 데이터에 따라 일부부터 시작하되 contract에는 다음 확장 지점을 둔다.

```text
macro_fit_score
industry_momentum_score
earnings_trend_score
price_momentum_score
valuation_score
supply_demand_score
risk_penalty_score
data_quality_score
confidence_score
total_score
```

## 작업 범위

1. sector config schema를 확인/정의한다.
2. sector scoring engine interface를 구현한다.
3. macro regime distribution과 feature/score inputs를 받아 sector score를 계산한다.
4. total_score를 component 기반으로 만든다.
5. reason_codes를 생성한다.
6. sector 추가가 config 중심으로 가능하게 한다.

## sector decision behavior

```text
score improving + confidence rising → gradual target increase candidate
score improving + volatility rising → limited increase or hold
score stable + overweight → stop new buys, hold
score falling + overweight → partial reduction candidate
score falling + risk pressure → reduction candidate
data quality poor → review required or hold
```

이 behavior는 order를 직접 만들지 않고 downstream allocation/rebalancing input으로만 전달한다.

## 테스트 요구사항

```text
- config-driven sector definition
- component score output
- total_score composition
- macro_fit_score behavior
- missing component fallback
- stale data fallback
- data_quality/confidence propagation
- reason_codes
- sector addition without core rewrite smoke test
```

## 완료 기준

- sector/asset score가 표준 contract로 생성된다.
- score decomposition이 가능하다.
- hardcoded sector weight가 없다.
