# Refactor Stop Conditions

목적: 모호한 판단이 필요한 경우 구현을 중단하도록 공통 중단 기준을 문서화한다.

---

## 1. 계좌 유형 중단 조건

- 계좌 유형(실전/모의)이 명확히 구분되지 않는 로직 변경 필요 시 → **REVIEW_REQUIRED**
- 계좌별 constraint가 코드에 하드코딩되어 있고 분리 방법이 불명확한 경우 → **REVIEW_REQUIRED**
- 계좌 안전 정책(최소 잔고, 주문 한도)이 코드에 없는 경우 → **RISK_REDUCE_ONLY**

## 2. Universe 중단 조건

- 자산 universe가 task 전제와 다른 테이블/파일에서 로드될 때 → **NO_ACTION**
- universe 변경이 전략 로직에 영향을 주는 경우 → **REVIEW_REQUIRED**
- universe 파일 경로가 환경에 따라 다를 수 있는 경우 → **HOLD**

## 3. Data Source 중단 조건

- 외부 데이터 소스 연결이 필요한 테스트 환경 변경 → **HOLD**
- 데이터 소스 스키마가 task 문서의 전제와 다를 때 → **NO_ACTION**
- 실시간 데이터와 백테스트 데이터를 같은 코드가 처리하는 경우 → **REVIEW_REQUIRED**

## 4. Execution Mode 중단 조건

- 실행 모드(실전/모의/백테스트)가 섞인 로직 분리가 필요한 경우 → **REVIEW_REQUIRED**
- 실행 모드 판단이 strategy 레이어에서 이루어지는 경우 → **HOLD**
- 모드 전환이 API 요청 파라미터에 따라 결정되는 경우 → **REVIEW_REQUIRED**

## 5. Score Formula 중단 조건

- 점수 공식(가중치, 파라미터)의 의미를 변경해야 할 때 → **NO_ACTION**
- 점수 계산 결과가 구조 변경으로 달라질 가능성이 있을 때 → **NO_ACTION**
- score 파이프라인이 strategy 외부로 노출되어야 할 때 → **REVIEW_REQUIRED**

## 6. Parameter Default 중단 조건

- config/*.yaml의 기본값 변경이 필요한 경우 → **NO_ACTION**
- 파라미터 기본값이 DB에 저장된 값과 충돌하는 경우 → **REVIEW_REQUIRED**
- 최적화 파라미터를 리팩토링 중에 변경해야 할 때 → **NO_ACTION**

## 7. Hard Constraint Boundary 중단 조건

- 계좌 hard constraint(최대 손실, 최소 현금)가 코드에 없거나 불명확한 경우 → **RISK_REDUCE_ONLY**
- 주문 실행 전 constraint 검증 로직이 없는 경우 → **RISK_REDUCE_ONLY**
- constraint 위반 시 동작이 정의되지 않은 경우 → **REVIEW_REQUIRED**

---

## 허용 Fallback

다음 상황에서는 안전한 대안으로 진행한다:

| 상황 | 허용 Fallback |
|------|---------------|
| 테스트 DB가 없는 경우 | `:memory:` SQLite 사용 |
| 외부 API 연결 불가 | Mock/Stub으로 테스트 격리 |
| 파일 경로 불명확 | 프로젝트 루트 기준 상대 경로 사용 |
| 옵셔널 기능 누락 | 해당 기능 skip 마크 후 진행 |

## 금지 Fallback

다음은 fallback으로 사용하지 않는다:

| 금지 상황 | 이유 |
|-----------|------|
| compatibility shim 생성 | 기술 부채 증가, shim 금지 원칙 위반 |
| 투자 로직 임의 변경 | 의도치 않은 수익/손실 변화 가능 |
| DB schema 무단 수정 | 기존 데이터 손상 위험 |
| 실전 계좌로 테스트 실행 | 실제 주문 발생 위험 |
| NO_ACTION 상황에서 임의 구현 | 미확인 가정 기반 구현 위험 |

---

## 판단 기준 정의

| 상태 | 정의 | 처리 방법 |
|------|------|-----------|
| **NO_ACTION** | 해당 코드/설정을 변경하지 않는다 | 변경 없이 다음 단계 진행 |
| **HOLD** | 더 많은 정보가 필요하여 지금 진행할 수 없다 | 중단 후 사용자에게 정보 요청 |
| **REVIEW_REQUIRED** | 사용자 확인 없이 진행할 수 없다 | 즉시 중단, 디버깅 보고서 작성 |
| **RISK_REDUCE_ONLY** | 안전한 방향으로만 변경한다 | 리스크를 줄이는 최소 변경만 허용 |
