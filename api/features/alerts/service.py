from __future__ import annotations

from typing import Any

from api.features.alerts.models import TelegramNotifyResult
from api.features.alerts.ports import IAlertsRepository


class AlertsService:
    def __init__(self, repo: IAlertsRepository) -> None:
        self._repo = repo

    def list_recent(self, limit: int) -> list[Any]:
        return self._repo.list_recent(limit)

    def mark_read(self, alert_id: int) -> dict:
        self._repo.mark_read(alert_id)
        return {"ok": True}

    def generate_alerts(self) -> dict:
        n = self._repo.generate_target_alerts()
        return {"ok": True, "created": n}

    def notify_telegram(self, level_filter: str = "danger") -> TelegramNotifyResult:
        from api.telegram_service import TelegramConfigError, TelegramSendError, send_telegram_message

        alerts, pending, skipped, _ = self._repo.get_pending_telegram_alerts(level_filter)

        if not alerts:
            return TelegramNotifyResult(ok=True, sent=0, message="전송할 알림 없음")
        if not pending:
            return TelegramNotifyResult(ok=True, sent=0, skipped=skipped, message="오늘 이미 전송한 알림입니다")

        level_emoji = {"danger": "🔴", "warning": "🟡", "info": "🔵"}
        lines = ["*TripleA 대시보드 알림*\n"]
        for alert, _ in pending:
            emoji = level_emoji.get(alert["level"], "⚪")
            lines.append(f"{emoji} *{alert['title']}*")
            if alert["message"]:
                lines.append(f"  {alert['message']}")
            lines.append("")

        text = "\n".join(lines).strip()

        try:
            send_telegram_message(text, parse_mode="Markdown")
            self._repo.record_telegram_logs(pending, "SENT")
            return TelegramNotifyResult(ok=True, sent=len(pending), skipped=skipped)
        except TelegramConfigError as e:
            raise RuntimeError(f"config:{e}") from e
        except TelegramSendError as e:
            error_message = str(e)
            self._repo.record_telegram_logs(pending, "FAILED", error=error_message)
            raise RuntimeError(f"send:{error_message}") from e
