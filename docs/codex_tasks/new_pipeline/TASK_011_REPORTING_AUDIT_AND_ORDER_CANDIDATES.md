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

# TASK 011 — Reporting, Audit, and Order Candidates

## 목적

decision explanation, audit log, order candidate generation을 구현한다. 단, 실제 주문 실행은 구현하지 않는다.

## 작업 범위

1. decision log writer를 구현한다.
2. reporting summary를 생성한다.
3. order candidate generator를 구현한다.
4. account/order constraint validation을 order candidate 전에 적용한다.
5. user review-ready output을 만든다.
6. execution engine은 read-only/order-candidate 단계로 제한한다.

## decision log 필수 필드

```text
date
data_snapshot_id
parameter_version
model_version
macro_scores
sector_scores
risk_budget_scores
target_weights
current_weights
rebalance_scores
account_constraints
decision
adjustment_intensity
reason_codes
warnings
```

## order candidate 필수 필드

```text
candidate_id
account_id
asset_id
action_candidate: BUY | HOLD | REDUCE | SELL | REVIEW_REQUIRED | BLOCKED
target_weight
current_weight
target_quantity_estimate
estimated_amount
cash_impact
constraint_result
reason_codes
warnings
requires_user_review
execution_allowed: false
```

`execution_allowed`는 이 태스크에서 반드시 `false`를 기본값으로 둔다.

## 설명 가능해야 하는 질문

```text
Why was this asset bought?
Why was this asset not sold?
Why was this asset reduced?
Why did this sector target weight increase?
Why was rebalancing skipped?
Which data was used?
What was the data as-of date?
Which parameter version was used?
Which model version was used?
Did the decision violate any account constraints?
What were transaction cost and tax implications?
```

## 테스트 요구사항

```text
- decision log serialization
- reason_codes preservation
- warnings preservation
- order candidate generation
- blocked candidate when hard constraint violated
- requires_user_review true for actionable candidate
- execution_allowed false by default
- no broker order API call
```

## 완료 기준

- user review 가능한 주문 후보가 생성된다.
- 실제 주문 실행은 없다.
- decision log로 판단 근거를 추적할 수 있다.
