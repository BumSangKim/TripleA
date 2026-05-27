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

# TASK 008 — Risk Budget and Constraint Gate

## 목적

attractiveness score만으로 비중을 정하지 않도록 portfolio/account risk budget과 hard constraint gate를 구현한다.

## 작업 범위

1. risk budget engine interface를 구현한다.
2. account constraint engine과 연결 가능한 constraint result contract를 구현한다.
3. portfolio-level risk와 account-level risk를 구분한다.
4. hard constraint는 score로 완화하지 않고 block 처리한다.
5. risk는 대부분 penalty/intensity 조정으로 반영하되, constraint는 별도 gate로 처리한다.

## 고려 요소

```text
expected return score
volatility
correlation
drawdown contribution
account constraints
liquidity
tax
transaction cost
existing position weight
data quality
confidence
```

## account type 예시

```text
taxable
ISA
pension
IRP
```

## hard constraint 예시

```text
account not eligible
IRP risky asset limit violation
leveraged/inverse/futures restriction
insufficient cash
minimum order size not satisfied
trading halt
missing account balance data
API state unknown
```

## 테스트 요구사항

```text
- portfolio risk budget output
- account-level risk budget output
- hard constraint blocks action
- risk penalty reduces intensity
- missing balance fallback
- invalid account type fallback
- data_quality poor does not increase risk
- constraint reason_codes
```

## 완료 기준

- risk budget output이 allocation input으로 사용 가능하다.
- hard constraint result가 명확하다.
- constraint를 score로 softening하지 않는다.
