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

# TASK 000 — Repository and Architecture Audit

## 목적

신규 Pipeline Architecture 구현 전에 저장소의 현재 구조를 감사하고, 재사용 가능한 인프라와 폐기해야 할 legacy 투자 판단 로직을 분리한다.

## 작업 범위

1. 저장소 구조를 점검한다.
2. 기존 전략/투자 판단 관련 모듈을 목록화한다.
3. 재사용 가능한 인프라를 식별한다.
4. 새 pipeline에서 사용하면 안 되는 legacy 판단 로직을 식별한다.
5. 결과를 문서화한다.

## 점검 대상 예시

```text
api/db.py
api/providers/*
api/strategy/*
config/*
tests/*
docs/*
scripts/*
```

실제 저장소 구조가 다르면 실제 구조 기준으로 조정한다.

## 산출물

다음 문서를 생성 또는 갱신한다.

```text
docs/SCORE_PIPELINE_ARCHITECTURE_AUDIT.md
docs/STATUS.md
```

`docs/SCORE_PIPELINE_ARCHITECTURE_AUDIT.md`에는 최소한 다음 섹션을 포함한다.

```text
1. Current repository map
2. Reusable infrastructure
3. Legacy strategy logic not to migrate
4. Candidate score pipeline module locations
5. Existing tests and gaps
6. Safety risks
7. Recommended implementation sequence
```

## 구현 금지

이 태스크에서는 코드 동작을 변경하지 않는다. 문서와 감사만 수행한다.

## 테스트 / 검증

- 문서가 생성되었는지 확인한다.
- legacy 판단 로직과 재사용 인프라가 명확히 분리되었는지 확인한다.
- `git diff --stat`으로 코드 변경이 없는지 확인한다.

## 완료 기준

- 새 Pipeline Architecture 구현 위치가 제안되어 있다.
- 재사용 가능 인프라와 금지 legacy 판단 로직이 구분되어 있다.
- 다음 태스크에서 타입/계약 정의를 시작할 수 있다.
