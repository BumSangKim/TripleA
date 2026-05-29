# Baseline Test Report

생성일: 2026-05-28  
목적: 리팩토링 전 테스트 상태 기록. 이후 변경의 회귀 여부 판단 기준.

---

## 실행 명령

```bash
.venv/bin/pytest -q
```

## 결과 요약

| 항목 | 값 |
|------|-----|
| 통과 | 518 |
| 실패 | 0 |
| 스킵 | 13 |
| 에러 | 0 |
| 실행 시간 | 5.24s |

## 스킵 항목 (13개)

아키텍처 계약 테스트 (tests/architecture/) — `api/features/`, `api/domain/` 미생성으로 skip:
- `test_features_router_no_db_import`
- `test_features_router_no_repository_import`
- `test_features_service_no_http_imports`
- `test_domain_no_fastapi_import`
- `test_domain_no_db_import`
- `test_service_no_http_exception`
- `test_service_no_get_conn`
- `test_service_no_sqlite3`
- `test_repository_no_fastapi`
- `test_service_has_class`
- `test_repository_has_class`
- 기타 2개 (환경 의존적 테스트 등)

## 실패 항목

없음.

## 참고사항

- 모든 518개 테스트가 통과하는 clean baseline.
- architecture 계약 테스트 11개는 `api/features/` 및 `api/domain/` 디렉터리 생성 후 활성화 예정.
- 리팩토링 후 이 baseline 대비 regression이 없어야 한다.
