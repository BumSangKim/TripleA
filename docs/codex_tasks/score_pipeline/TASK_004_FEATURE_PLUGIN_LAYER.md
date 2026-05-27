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

# TASK 004 — Feature Plugin Layer

## 목적

raw data를 normalized feature로 변환하는 독립 plugin layer를 만든다. 병목 데이터, macro data, sector data, price data 등은 모두 feature plugin으로 확장 가능해야 한다.

## 작업 범위

1. feature plugin interface를 정의한다.
2. feature registry를 구현한다.
3. feature output contract를 적용한다.
4. 최소 reference plugin을 구현한다.
5. config 기반 feature enable/disable 구조를 만든다.

## feature output 필수 요소

```text
feature_id
feature_name
asset_id or sector_id or macro_id
raw_value
normalized_value
confidence
data_quality
as_of_date
source
parameter_version
model_version
reason_codes
warnings
```

## plugin 설계 원칙

- plugin은 서로 독립적이어야 한다.
- plugin은 downstream allocation을 직접 알면 안 된다.
- plugin은 buy/sell/order candidate를 생성하면 안 된다.
- plugin 추가가 core engine rewrite를 요구하면 안 된다.

## 최소 reference plugin 예시

저장소 데이터 상황에 따라 실제 가능한 항목을 선택한다.

```text
price_momentum_feature
volatility_feature
fx_change_feature
export_yoy_feature
```

데이터가 부족하면 synthetic fixture 기반 테스트 plugin을 먼저 둔다.

## 테스트 요구사항

```text
- plugin registration
- plugin execution
- normalized value range
- missing input fallback
- stale input fallback
- parameter_version propagation
- data_quality propagation
- plugin independence
```

## 완료 기준

- feature plugin을 하나 이상 실행할 수 있다.
- feature output이 표준 contract를 따른다.
- downstream score layer가 feature output을 소비할 준비가 된다.
