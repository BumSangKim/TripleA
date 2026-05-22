# 2026-05-22 알림 중복 방지 연결

## 작업 범위

`trading-modes-development-plan.md`의 알림 설계 중 `notification_logs` 기반 Telegram 중복 방지 정책을 구현했다. 실전 투자와 모의 투자 주문 항목은 제외했다.

## 작업 내용

- `POST /api/alerts/notify/telegram` 전송 전에 오늘 이미 전송한 알림인지 확인하도록 했다.
- dedup key는 날짜, 레벨, 카테고리, 제목을 조합해 만든다.
- 전송 성공 시 `notification_logs`에 `TELEGRAM`, `SENT`, `dedup_key`, 메시지, `sent_at`을 저장한다.
- 같은 알림을 다시 전송하면 Telegram API를 호출하지 않고 `sent=0`, `skipped`를 반환한다.
- 전송 실패 시 `notification_logs`에 `FAILED`와 마스킹된 오류 메시지를 저장한다.
- Telegram Bot 토큰이 오류 문자열에 포함되어도 API 응답과 DB 로그에서는 `***`로 마스킹한다.
- 알림 endpoint 테스트를 추가했다.
  - 성공 전송 로그 저장
  - 동일 알림 중복 전송 차단
  - 실패 시 토큰 마스킹

## 미작업 내용

- Telegram 채널 설정을 `notification_channels`에서 읽는 흐름은 아직 없다. 현재는 기존처럼 환경변수와 `API_KEY/TELEGRAM_KEY` fallback을 사용한다.
- 알림별 read 처리 자동화는 아직 없다. 중복 방지는 전송 로그 기준으로만 동작한다.
- 계좌별 엔진/RiskBudget 기반 고급 알림 생성은 아직 기본 목표 이탈 알림 수준이다.

## 레거시 확인

- 레거시 수집 파이프라인이나 주문 실행 스크립트는 추가하지 않았다.
- 변경 범위는 현재 FastAPI 알림 endpoint, 테스트, 개발 로그로 제한했다.

## 검증

- `PYTHONPATH=. .venv/bin/python -m pytest tests/test_api_endpoints.py::TestAlertsEndpoints` 통과

## 다음 실행 참고

1. `notification_channels`에 Telegram 설정을 저장/조회하는 API를 추가한다.
2. `notification_logs` 이력을 UI에서 확인할 수 있는 설정/알림 화면을 연결한다.
3. `RiskBudget`과 계좌별 엔진을 리밸런싱 결과 생성 경로에 붙인다.
