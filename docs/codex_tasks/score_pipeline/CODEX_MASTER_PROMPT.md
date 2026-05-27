# Codex Master Prompt — Score Pipeline Architecture

아래 지시를 저장소 루트에서 순서대로 수행해줘.

## 목표

TripleA 저장소에 신규 Pipeline Architecture를 구현한다. 이것은 Legacy 호환 마이그레이션이 아니다. 기존 투자 판단 엔진을 보존하거나 감싸는 것이 아니라, 재사용 가능한 인프라만 식별하여 활용하고 전략 판단 로직은 score-based pipeline으로 새로 정렬한다.

## 반드시 먼저 읽을 문서

작업 시작 전 다음 문서를 확인해라. 파일이 없으면 동일 목적의 문서를 찾아 읽고, 없다는 사실을 status에 기록해라.

```text
MASTER_DEVELOPMENT_GUIDE.md
AGENTS.md
docs/PROJECT_CONTEXT.md
docs/PHASE_ROADMAP.md
docs/CODEX_WORKFLOW.md
```

그리고 이 태스크 팩의 파일을 아래 순서대로 하나씩 수행해라.

```text
docs/codex_tasks/score_pipeline/TASK_000_REPOSITORY_AND_ARCHITECTURE_AUDIT.md
docs/codex_tasks/score_pipeline/TASK_001_PIPELINE_CONTRACTS_AND_TYPES.md
docs/codex_tasks/score_pipeline/TASK_002_CONFIGURATION_AND_PARAMETER_REGISTRY.md
docs/codex_tasks/score_pipeline/TASK_003_DATA_SNAPSHOT_AND_QUALITY_LAYER.md
docs/codex_tasks/score_pipeline/TASK_004_FEATURE_PLUGIN_LAYER.md
docs/codex_tasks/score_pipeline/TASK_005_SCORE_LAYER_CORE.md
docs/codex_tasks/score_pipeline/TASK_006_MACRO_REGIME_ENGINE.md
docs/codex_tasks/score_pipeline/TASK_007_SECTOR_SCORING_ENGINE.md
docs/codex_tasks/score_pipeline/TASK_008_RISK_BUDGET_AND_CONSTRAINT_GATE.md
docs/codex_tasks/score_pipeline/TASK_009_ALLOCATION_AND_REBALANCING_ENGINE.md
docs/codex_tasks/score_pipeline/TASK_010_BACKTEST_INTEGRATION_AND_LEAKAGE_TESTS.md
docs/codex_tasks/score_pipeline/TASK_011_REPORTING_AUDIT_AND_ORDER_CANDIDATES.md
docs/codex_tasks/score_pipeline/TASK_012_FINAL_VERIFICATION_COMMIT_PUSH.md
```

## 실행 규칙

각 태스크는 독립 완료 단위다.

```text
1. 현재 태스크 파일을 읽는다.
2. 저장소 상태와 관련 코드를 점검한다.
3. 최소 변경 범위를 정한다.
4. 현재 태스크 범위만 구현한다.
5. 테스트를 추가하거나 수정한다.
6. 관련 테스트를 실행한다.
7. 실패하면 수정 후 다시 테스트한다.
8. 통과할 때까지 4~7을 반복한다.
9. 태스크 완료 상태와 변경 파일, 테스트 결과, 남은 위험을 기록한다.
10. 다음 태스크로 넘어간다.
```

## 절대 금지

```text
LegacyReferenceEngine, LegacyBridge, Legacy Golden Master, Legacy Shadow Compare 생성 금지
기존 TripleAAllocator, MacroEngine, RiskBudgetEngine의 판단 로직을 새 엔진 내부로 그대로 복사 금지
단일 threshold로 risk-on/risk-off 전환 금지
dominant regime label을 fixed weight로 직접 매핑 금지
raw data에서 직접 buy/sell 생성 금지
실계좌 주문 실행 또는 자동 실행 추가 금지
광범위 리팩터링 금지
테스트 실패 무시 금지
```

## 완료 후

모든 태스크 완료 후 전체 테스트와 안전 점검을 실행하고, 문제가 없으면 다음 형식으로 커밋 및 푸쉬한다.

```bash
git status --short
git add <changed files>
git commit -m "Implement new score-based pipeline architecture"
git push
```

커밋 전에는 비밀키, DB, 캐시, node_modules, 빌드 산출물, 로컬 데이터가 포함되지 않았는지 확인한다.
