# Architecture Contract

생성일: 2026-05-28  
목적: import-linter와 architecture test가 검증할 레이어별 import 계약을 정의한다.

---

## 1. Feature 파일별 책임

각 feature는 `api/features/<feature_name>/` 디렉터리를 가진다.

| 파일 | 책임 | 허용 import |
|------|------|-------------|
| `router.py` | FastAPI route 정의 | fastapi, feature models, service (Protocol) |
| `service.py` | 비즈니스 로직 | domain, core, Port Protocols |
| `repository.py` | DB 접근 구현체 | sqlite3, domain models |
| `models.py` | 요청/응답 모델 | pydantic |
| `ports.py` | Port Protocol 정의 | typing, domain models |

### 현재 Feature 목록

- **dashboard** — 대시보드 조회 및 포트폴리오 요약
- **rebalancing** — 리밸런싱 계획 및 실행
- **backtests** — 백테스트 실행 및 결과 조회
- **orders** — 주문 생성, 조회, 취소

---

## 2. Import 규칙

### domain 순수성 규칙
- `api/domain/` → FastAPI, sqlite3, requests, HTTPException import 금지
- `api/domain/` → `api/features/` import 금지

### strategy 고립 규칙
- `api/strategy/` → FastAPI, HTTPException import 금지
- `api/strategy/` → `api/features/` import 금지

### service 규칙
- `api/features/*/service.py` → `sqlite3`, `get_conn`, SQL, FastAPI, HTTPException import 금지
- service는 Port Protocol만 알고, Repository 구현체를 직접 import하지 않는다

### repository 규칙
- `api/features/*/repository.py` → FastAPI, router, service, strategy import 금지
- repository는 DB 연결 팩토리와 domain 모델만 import한다

### router 규칙
- `api/features/*/router.py` → repository, db.connection 직접 import 금지
- router는 Service(또는 Protocol)만 의존성 주입으로 받는다

### db 접근 규칙
- `api/db.py` → 연결 팩토리 역할만 허용
- feature service는 `api/db.py`를 직접 import하지 않는다

### pipeline manifest 규칙
- `config/pipelines/investment_decision.yaml` declares the review-only
  investment decision pipeline.
- `api/score_pipeline/pipeline_manifest.py` loads and validates the manifest.
- `auto_execution_allowed` must remain `false`.
- Conservative fallback actions are limited to `NO_ACTION`, `HOLD`,
  `REVIEW_REQUIRED`, and `RISK_REDUCE_ONLY`.
- `hard_constraint_filter` must precede `order_candidate_generation`.
- `order_candidate_generation` is manual-review candidate generation only; it
  is not broker execution.

### root orphan 처리 원칙
- Root-level `api/*.py` files are inventory-controlled by
  `tests/architecture/test_modular_monolith_import_boundaries.py`.
- Owner-unresolved root files must stay allowlisted until an explicit relocation
  task assigns an owner.
- Relocations must avoid shims unless a task explicitly allows compatibility
  adapters.
- Strategy files must not import feature modules or root trade-data services.

---

## 3. DomainError 계약

- `DomainError`는 HTTP status_code 필드를 가지지 않는다.
- HTTP status 매핑은 오직 `api/core/errors.py`에서만 정의한다.
- 모든 도메인 에러는 `DomainError`를 상속한다.

### DomainError 계층

```python
DomainError
├── AccountNotFoundError
├── OrderBlockedError
├── ConstraintViolationError
├── DataQualityError
└── StrategyValidationError
```

### HTTP Status 매핑 (core/errors.py)

| DomainError 타입 | HTTP Status |
|-----------------|-------------|
| AccountNotFoundError | 404 |
| OrderBlockedError | 422 |
| ConstraintViolationError | 422 |
| DataQualityError | 422 |
| StrategyValidationError | 422 |
| DomainError (기타) | 500 |

---

## 4. Orders 분류

orders feature는 다음을 포함한다:
- 시장가/지정가 주문 생성
- 주문 상태 조회
- 주문 취소
- 주문 이력 조회

orders feature는 투자 판단(strategy) 로직을 직접 호출하지 않는다.  
투자 판단은 rebalancing feature에서 수행하며, orders는 실행 지시만 처리한다.

---

## 5. Orchestration Feature

다른 feature를 조율하는 feature는 다음과 같다:

- **rebalancing**: strategy → orders 흐름을 조율한다.
  - strategy 결과(order candidates)를 orders feature로 전달한다.
  - 계좌 constraint 확인 후 주문 실행을 승인한다.

---

## 6. 계약 위반 시 처리

- `tests/architecture/test_import_contracts.py` — import 계약 위반 검출
- `tests/architecture/test_feature_contracts.py` — feature 구조 계약 위반 검출
- `tests/architecture/test_modular_monolith_import_boundaries.py` — modular
  monolith boundary, root orphan, and selected relocation guardrails
- `tests/architecture/test_pipeline_manifest_file.py` — manifest file contract
- `tests/architecture/test_pipeline_manifest_contract.py` — manifest loader and
  validation contract
- `tests/architecture/test_strategy_sqlite_baseline.py` — current strategy
  sqlite baseline guard
- `.importlinter` 또는 `pyproject.toml [tool.importlinter]` — 자동 lint 검증

계약 위반이 발견되면 해당 파일의 리팩토링을 우선 진행한다.
