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

# TASK 010 — Backtest Integration and Leakage Tests

## 목적

새 pipeline을 historical simulation에 연결하고, future-data leakage를 방지하는 테스트를 강화한다.

## 작업 범위

1. 기존 backtest engine 구조를 점검한다.
2. pipeline output을 backtest clock에서 호출할 수 있게 연결한다.
3. simulated decision date 기준 데이터만 사용하도록 제한한다.
4. portfolio state update를 allocation/rebalancing 결과와 연결한다.
5. transaction cost model hook을 연결한다.
6. backtest metrics를 생성한다.

## 필수 metrics

```text
CAGR
MDD
annualized volatility
Sharpe
Sortino
Calmar
turnover
cost-adjusted return
regime-by-regime performance
contribution analysis
stress-period performance
parameter sensitivity hook
```

세금 모델은 구현 전이면 hook과 TODO/status를 남기되, tax impact를 무시하고 production-ready라고 표시하면 안 된다.

## leakage 방지 필수 테스트

```text
- future price unavailable at decision date
- macro release after decision date unavailable
- earnings after announcement date only
- revised data not treated as originally available
- parameter valid_from respected
- asset universe as-of date respected
```

## strategy rejection / warning 조건

```text
future data dependency
single-regime overfit
extreme turnover
collapse after costs
unexplained performance
account constraint violation
MDD increase without adequate return improvement
```

## 테스트 요구사항

```text
- simulation clock behavior
- pipeline called per rebalance date
- no future data leakage
- cost-adjusted metrics
- turnover metrics
- conservative fallback in missing data backtest
- reproducibility with same parameter_version
```

## 완료 기준

- 새 pipeline을 사용하는 backtest smoke test가 통과한다.
- leakage 방지 테스트가 존재한다.
- 백테스트 결과가 decision/audit layer로 전달 가능하다.
