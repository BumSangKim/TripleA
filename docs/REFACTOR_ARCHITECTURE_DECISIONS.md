# Refactor Architecture Decisions

생성일: 2026-05-28  
목적: 리팩토링에서 확정한 설계 결정을 코드베이스 문서로 고정한다.

---

## 1. 수직 슬라이스 (Vertical Slice)

- 기능 단위로 `api/features/<feature_name>/` 디렉터리를 만든다.
- 각 feature 디렉터리는 `router.py`, `service.py`, `repository.py`, `models.py`를 포함한다.
- feature 간 직접 import는 금지한다. 공유 로직은 `api/domain/` 또는 `api/core/`로 추출한다.

## 2. Port/Protocol 패턴

- Service는 Repository를 직접 import하지 않는다.
- Service는 Port Protocol(인터페이스)에 의존한다.
- Repository는 Port Protocol의 DB-backed 구현체다.
- Port Protocol은 `typing.Protocol`로 정의한다.

## 3. Class-Only Service/Repository

- Service와 Repository는 반드시 `class`로 구현한다.
- 함수형(standalone function) 서비스/리포지토리 구현은 금지한다.
- 기존 함수형 코드를 마이그레이션할 때 클래스로 래핑한다.

## 4. Error Payload 표준

- `DomainError`는 HTTP status_code를 가지지 않는다.
- HTTP status 매핑은 `api/core/errors.py`에서만 한다.
- 에러 응답 payload는 `{"error": "<code>", "message": "<str>", "details": <dict|list|null>}` 형식이다.
- `details`가 None이면 응답에서 생략한다.

## 5. No-Shim 이동 원칙

- `api/db.py`, `api/modes.py`, `api/providers.py`, `api/kis.py`에 compatibility shim을 생성하지 않는다.
- 이동 시 기존 모듈의 public API를 직접 참조하는 코드를 모두 수정한다.
- shim 없이 진행이 불가능하면 즉시 중단하고 사용자에게 보고한다.

---

## 6. 레이어별 책임

### `api/features/<feature>/router.py`
- FastAPI route 정의만 담당한다.
- repository나 db.connection을 직접 import하지 않는다.
- Service 인스턴스를 의존성 주입으로 받는다.

### `api/features/<feature>/service.py`
- 비즈니스 로직을 담당한다.
- `sqlite3.Connection`, `get_conn`, SQL, `FastAPI`, `HTTPException`을 직접 알면 안 된다.
- Port Protocol에 의존한다.

### `api/features/<feature>/repository.py`
- DB-backed Port Protocol 구현체다.
- FastAPI, router, service, strategy를 직접 import하지 않는다.
- SQL과 DB 연결만 다룬다.

### `api/domain/`
- DomainError 계층과 도메인 규칙을 담는다.
- FastAPI, DB, HTTP를 알지 못한다.

### `api/core/`
- FastAPI app 설정, exception handler, 공통 미들웨어를 담는다.
- DomainError → HTTP 응답 변환 책임을 가진다.

### `api/db.py`
- 현재: DB 연결 및 스키마 마이그레이션 함수 모음.
- 리팩토링 후: 연결 팩토리만 남기거나 feature별 repository로 분산한다.
- shim 생성 금지.

### `api/providers.py`
- 현재: 데이터 provider 추상화.
- 리팩토링 후: feature별 Port Protocol로 이동.

### `api/brokers/`
- KIS 등 브로커 클라이언트를 담는다.
- 현재 `api/kis.py`의 역할을 이곳으로 이동한다.

---

## 7. Shim 금지 대상 및 제거 기준

| 파일 | 제거 기준 |
|------|-----------|
| `api/db.py` | 모든 참조가 feature repository 또는 `api/core/db.py`로 이동 완료 |
| `api/modes.py` | TradingMode가 `api/domain/` 또는 feature로 이동 완료 |
| `api/providers.py` | Port Protocol로 대체 완료 |
| `api/kis.py` | `api/brokers/kis/` 구현으로 완전 교체 완료 |

---

## 8. 투자 판단 로직 보호

- `api/strategy/` 하위 투자 알고리즘은 이번 구조 리팩토링에서 변경하지 않는다.
- 리팩토링은 import 경로와 레이어 구조만 변경하며, 알고리즘 의미는 보존한다.
