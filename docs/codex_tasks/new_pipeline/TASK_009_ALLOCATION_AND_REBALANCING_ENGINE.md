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

# TASK 009 — Allocation and Rebalancing Engine

## 목적

score flow, risk budget, hard constraints를 기반으로 target allocation range/current target weight와 rebalancing intensity를 계산한다.

## allocation 원칙

target은 fixed weight가 아니라 range다.

```json
{
  "asset_id": "string",
  "min_weight": 0.0,
  "base_weight": 0.0,
  "max_weight": 0.0,
  "current_target": 0.0
}
```

## 작업 범위

1. allocation engine interface를 구현한다.
2. sector score, macro regime distribution, risk budget을 입력으로 받는다.
3. min/base/max/current_target 구조를 구현한다.
4. target change limit을 적용한다.
5. rebalancing engine interface를 구현한다.
6. rebalancing score/intensity를 계산한다.
7. mechanical restore-to-old-weight 방식이 되지 않도록 한다.

## allocation flow

```text
Base Weight
+ Macro Regime Adjustment
+ Sector Score Adjustment
+ Conviction Adjustment
- Risk Penalty Adjustment
- Concentration Penalty
- Cost Penalty
- Tax Penalty
→ Preliminary Target Weight
→ Hard Constraint Filter
→ Final Target Weight
```

## rebalancing score

```text
Rebalancing Score
= Weight Drift Score
+ Conviction Change Score
+ Risk Limit Pressure Score
+ Cash Availability Score
+ Cost Efficiency Score
+ Tax Efficiency Score
- Turnover Penalty
```

## satellite winner policy

고성장 satellite가 목표 비중을 초과했다고 기계적으로 매도하지 않는다.

```text
overweight + score stable → stop new buys, hold
overweight + score improving → consider gradual target expansion
overweight + score falling → partial reduction candidate
overweight + risk limit pressure → reduction candidate
score improving + risk budget available → buy candidate
score improving + volatility spike → hold or limited buy
data quality poor → review required
```

## 테스트 요구사항

```text
- target range output
- current_target within range
- gradual change limit
- macro/sector/risk input propagation
- overweight winner hold behavior
- improving overweight gradual expansion candidate
- falling overweight reduction candidate
- turnover limit
- no direct dominant regime fixed weight mapping
```

## 완료 기준

- allocation target과 rebalancing intensity가 생성된다.
- 기계적 리밸런싱이 아니라 score/intensity 기반이다.
- order candidate는 아직 생성하지 않거나 다음 task로 넘긴다.
