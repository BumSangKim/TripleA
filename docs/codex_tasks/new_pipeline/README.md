# TripleA New Pipeline Architecture Codex Task Pack

이 폴더는 “마이그레이션 가이드 평가”에서 정리한 방향을 Codex가 순차적으로 실행할 수 있도록 분해한 태스크 팩이다.

핵심 결론:

- 이것은 Legacy 호환 마이그레이션이 아니다.
- 새 Pipeline Architecture를 기준으로 구현한다.
- 기존 투자 판단 로직은 새 구조에 그대로 편입하지 않는다.
- 재사용 가능한 인프라와 투자 판단 로직을 분리한다.
- 모든 전략 판단은 score flow를 따른다.
- hard constraint는 score보다 우선한다.
- 자동 주문 실행은 범위 밖이다.

## 실행 순서

```text
TASK_000_REPOSITORY_AND_ARCHITECTURE_AUDIT.md
TASK_001_PIPELINE_CONTRACTS_AND_TYPES.md
TASK_002_CONFIGURATION_AND_PARAMETER_REGISTRY.md
TASK_003_DATA_SNAPSHOT_AND_QUALITY_LAYER.md
TASK_004_FEATURE_PLUGIN_LAYER.md
TASK_005_SCORE_LAYER_CORE.md
TASK_006_MACRO_REGIME_ENGINE.md
TASK_007_SECTOR_SCORING_ENGINE.md
TASK_008_RISK_BUDGET_AND_CONSTRAINT_GATE.md
TASK_009_ALLOCATION_AND_REBALANCING_ENGINE.md
TASK_010_BACKTEST_INTEGRATION_AND_LEAKAGE_TESTS.md
TASK_011_REPORTING_AUDIT_AND_ORDER_CANDIDATES.md
TASK_012_FINAL_VERIFICATION_COMMIT_PUSH.md
```

## Codex 시작 프롬프트

`CODEX_MASTER_PROMPT.md` 내용을 Codex 첫 입력으로 사용한다.

## 완료 기준

모든 태스크가 완료되면 다음 상태여야 한다.

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
→ User Review
```

실제 주문 실행은 생성하지 않는다.
