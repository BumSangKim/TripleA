# TripleA Score Pipeline Architecture — Codex Task

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

# TASK 002 — Configuration and Parameter Registry

## 목적

전략 파라미터를 코드 하드코딩에서 분리하고, 버전/유효기간/근거를 가진 데이터로 관리한다.

## 작업 범위

1. 현재 config 구조를 조사한다.
2. parameter registry schema를 정의한다.
3. 다음 항목을 config로 관리할 수 있게 한다.

```text
score weights
smoothing span / EMA span
lookback windows
volatility normalization windows
sector min/base/max weight
asset min/base/max weight
account risk limits
turnover limits
transaction cost assumptions
tax assumptions
rebalancing bands
fallback policy
```

4. parameter loader를 구현한다.
5. parameter_version이 score/decision output으로 전파될 수 있게 contract와 연결한다.

## 권장 파일 예시

실제 저장소 관례에 맞춰 조정한다.

```text
config/parameters/default.yaml
config/parameters/backtest.yaml
config/parameters/schema.yaml
```

## parameter metadata 필수 필드

```text
name
value
version
valid_from
valid_to
source
reason
approved
```

가능하면 다음 필드도 포함한다.

```text
backtest_result
walk_forward_result
rollback_condition
affected_modules
```

## fallback 정책

필수 parameter가 없거나 invalid이면 다음 중 하나로 처리한다.

```text
NO_ACTION
HOLD
REVIEW_REQUIRED
RISK_REDUCE_ONLY
```

절대 다음으로 default하지 않는다.

```text
BUY
INCREASE_RISK
FORCE_REBALANCE
AUTO_EXECUTE
```

## 테스트 요구사항

```text
- valid parameter load
- missing parameter fallback
- invalid type fallback
- valid_from / valid_to handling
- parameter_version propagation
- no hardcoded strategy parameter smoke test
```

## 완료 기준

- 전략 파라미터가 설정 파일에서 로드된다.
- invalid/missing parameter가 보수적 fallback으로 처리된다.
- 테스트가 통과한다.
