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

# TASK 001 — Pipeline Contracts and Types

## 목적

모든 엔진이 공유할 표준 계약과 타입을 정의한다. downstream module은 upstream 내부 구현이 아니라 contract만 소비해야 한다.

## 핵심 설계

필수 decision flow:

```text
Raw Data
→ Feature Layer
→ Score Layer
→ Macro Regime Score Distribution
→ Sector / Asset Score
→ Risk Budget Score
→ Allocation Score
→ Rebalancing Intensity Score
→ Hard Constraint Filter
→ Order Candidate
```

## 작업 범위

1. pipeline contract module 위치를 정한다.
2. 다음 공통 타입을 정의한다.

```text
DataQualityMetadata
ParameterVersionRef
ModelVersionRef
ReasonCode
DecisionWarning
FeatureOutput
ScoreOutput
MacroRegimeDistribution
SectorScoreOutput
RiskBudgetOutput
AllocationTargetRange
RebalancingDecision
ConstraintResult
OrderCandidate
DecisionLogRecord
```

3. 모든 score 기반 output은 다음 필드를 포함하거나 명시적으로 매핑 가능해야 한다.

```text
score
previous_score
score_change
confidence
data_quality
stability
adjustment_intensity
reason_codes
as_of_date
parameter_version
model_version
```

4. serialization 가능한 구조로 만든다.
5. Python 3.10 이상 기준으로 구현한다.

## 권장 구현 방식

- dataclass 또는 pydantic 중 저장소 관례에 맞춘다.
- 투자 판단 수식은 아직 구현하지 않는다.
- 타입과 검증 helper만 구현한다.
- 기본값은 공격적 행동이 아니라 conservative fallback으로 둔다.

## 테스트 요구사항

다음 테스트를 추가한다.

```text
- contract 객체 생성 테스트
- score range validation 테스트
- missing required field 테스트
- reason_codes / warnings serialization 테스트
- conservative fallback enum 테스트
- downstream compatibility smoke test
```

## 금지

```text
기존 엔진 로직 호출 금지
buy/sell 로직 구현 금지
threshold 기반 regime switch 구현 금지
```

## 완료 기준

- 공통 contract가 import 가능하다.
- serialization 테스트가 통과한다.
- score output 표준 필드가 검증된다.
