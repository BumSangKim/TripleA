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

# TASK 003 — Data Snapshot and Quality Layer

## 목적

raw data와 derived data를 분리하고, 모든 feature/score가 데이터 출처·시점·품질을 추적할 수 있게 한다.

## 작업 범위

1. 현재 데이터 저장/로드 구조를 조사한다.
2. raw/feature/score/decision data 분리 원칙을 코드와 문서에 반영한다.
3. DataQualityMetadata를 실제 데이터 로딩 경로에 연결한다.
4. historical snapshot reconstruction에 필요한 최소 구조를 정의한다.
5. missing/stale/anomalous data 처리 정책을 구현한다.

## 필수 metadata

```text
source
as_of_date
updated_at
quality_score
missing_ratio
is_stale
warnings
```

## stale/missing 처리 정책

데이터 품질이 낮으면 다음 중 하나로 처리한다.

```text
reduce_signal_weight
hold
review_required
use_conservative_fallback
risk_reduce_only
```

데이터 품질 불량 상태에서 risk를 증가시키면 안 된다.

## 백테스트 시점 원칙

백테스트는 simulated decision date에 이용 가능했던 데이터만 사용해야 한다.

금지:

```text
future price 사용
발표 전 earnings 사용
수정된 macro data를 과거에 이미 알았던 것처럼 사용
future ETF constituents 사용
survivorship bias 미처리
```

## 테스트 요구사항

```text
- DataQualityMetadata 생성
- missing data detection
- stale data detection
- anomalous data warning
- as_of_date filtering
- no future data leakage fixture
- poor data quality does not increase risk
```

## 완료 기준

- 데이터 로딩 결과에 quality metadata가 붙는다.
- feature/score layer가 metadata를 받을 수 있다.
- leakage 방지 테스트가 존재한다.
