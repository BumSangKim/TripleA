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

# TASK 006 — Macro Regime Engine

## 목적

macro score들을 이용해 macro regime label 하나가 아니라 regime score distribution을 생성한다.

## 필수 출력

```json
{
  "regime_distribution": {
    "risk_on_growth": 0.0,
    "neutral": 0.0,
    "inflation_pressure": 0.0,
    "recession_risk": 0.0,
    "volatility_stress": 0.0
  },
  "dominant_regime": "neutral",
  "confidence": 0.0,
  "data_quality": 0.0,
  "reason_codes": [],
  "as_of_date": "YYYY-MM-DD",
  "parameter_version": "string",
  "model_version": "string"
}
```

## 작업 범위

1. macro regime engine interface를 구현한다.
2. macro score inputs를 contract 기반으로 받는다.
3. regime distribution normalization을 구현한다.
4. dominant_regime은 설명용 필드로만 제공한다.
5. allocation fixed weight로 직접 연결하지 않는다.
6. missing/stale macro data fallback을 구현한다.

## 입력 카테고리

가용 데이터에 따라 일부부터 시작하되 구조는 확장 가능해야 한다.

```text
interest rates
inflation
FX
liquidity
credit spreads
volatility
economic activity
export/import data
commodity prices
market trend
market breadth
```

## 테스트 요구사항

```text
- regime_distribution output
- normalization behavior
- dominant_regime explanation-only
- multiple macro input handling
- missing macro input fallback
- stale macro input fallback
- confidence/data_quality propagation
- no direct fixed weight mapping
```

## 완료 기준

- macro regime distribution을 생성할 수 있다.
- 단일 threshold regime switch가 없다.
- allocation/rebalancing이 사용할 수 있는 contract를 제공한다.
