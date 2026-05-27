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

# TASK 012 — Final Verification, Commit, and Push

## 목적

모든 태스크 완료 후 저장소 전체 검증을 수행하고, 안전한 변경만 커밋·푸쉬한다.

## 작업 범위

1. 모든 변경 파일을 확인한다.
2. 전체 테스트를 실행한다.
3. lint/typecheck/build 명령이 있으면 실행한다.
4. live execution / automatic execution이 추가되지 않았는지 점검한다.
5. secret/local artifact가 commit 대상에 포함되지 않았는지 점검한다.
6. docs/status를 최종 갱신한다.
7. 커밋하고 푸쉬한다.

## 필수 점검 명령

저장소에 맞는 명령을 사용하되, 최소한 다음을 수행한다.

```bash
git status --short
git diff --stat
git diff --check
python -m pytest
```

프론트엔드가 있으면 package manager를 확인한 뒤 가능한 명령을 실행한다.

```bash
npm test
npm run lint
npm run build
```

해당 명령이 정의되어 있지 않으면 “not available”로 기록한다.

## 안전 점검

다음 파일/디렉터리가 staging에 포함되면 안 된다.

```text
.env
API_KEY/
*.key
*.pem
*.sqlite
*.db
__pycache__/
.pytest_cache/
web/.next/
web/node_modules/
data/
pipeline.log
.DS_Store
```

## architecture compliance checklist

```text
[ ] No LegacyReferenceEngine
[ ] No LegacyBridge
[ ] No Legacy Golden Master / Shadow Compare
[ ] No single-threshold regime switch
[ ] No raw data to buy/sell shortcut
[ ] No dominant regime to fixed weight shortcut
[ ] Hard constraints block actions
[ ] Poor data quality cannot increase risk
[ ] Parameters are loaded from config/registry
[ ] Backtest has leakage prevention tests
[ ] Order candidates require user review
[ ] execution_allowed defaults to false
[ ] No broker order call added
```

## status 문서 갱신

`docs/STATUS.md` 또는 저장소의 canonical status 문서에 다음을 기록한다.

```text
- completed tasks
- changed files
- tests run
- test results
- known limitations
- intentionally deferred items
- whether commit/push was completed
```

## 커밋/푸쉬

검증이 통과하면 다음을 실행한다.

```bash
git add <approved changed files>
git commit -m "Implement new score-based pipeline architecture"
git push
```

## 실패 시 처리

테스트 또는 안전 점검이 실패하면 커밋하지 않는다. 실패 원인, 명령, 수정 필요 파일을 보고하고 해당 태스크 또는 이전 태스크로 돌아가 수정한다.

## 완료 기준

- 전체 검증이 통과한다.
- 금지 패턴이 없다.
- commit/push가 완료되었거나, 실패 사유가 명확히 기록되어 있다.
