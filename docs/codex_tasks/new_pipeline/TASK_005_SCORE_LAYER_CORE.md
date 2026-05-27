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

# TASK 005 — Score Layer Core

## 목적

feature output을 comparable score로 변환하는 score layer를 구현한다. 모든 score는 normalized, smoothed, confidence-adjusted, data-quality-adjusted 되어야 한다.

## 필수 score flow

```text
raw_feature
→ normalized_score
→ smoothed_score
→ confidence_adjusted_score
→ data_quality_adjusted_score
→ decision_score
```

## 작업 범위

1. score calculator interface를 정의한다.
2. score registry를 구현한다.
3. smoothing helper를 구현한다.
4. confidence adjustment helper를 구현한다.
5. data quality penalty helper를 구현한다.
6. previous_score / score_change 계산 구조를 구현한다.
7. reason code를 생성한다.

## EMA/span 정책

- span은 config parameter로 관리한다.
- span이 missing/invalid이면 conservative fallback을 사용한다.
- 사용자가 외부 이벤트 대응 목적으로 span을 조정할 수 있도록 parameter registry와 연결한다.
- 단, span 변경 자체가 즉시 buy/sell을 유발하면 안 된다.

## 테스트 요구사항

```text
- score range 0.0~1.0 또는 명시 range 검증
- smoothing behavior
- span parameter behavior
- invalid span fallback
- confidence adjustment
- data quality penalty
- previous_score / score_change
- reason_codes output
- no threshold switch
```

## 완료 기준

- feature에서 score까지 변환할 수 있다.
- score output이 표준 contract를 따른다.
- smoothing/confidence/data_quality 조정이 테스트된다.
