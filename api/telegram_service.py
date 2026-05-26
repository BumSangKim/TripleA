"""
Shared Telegram Bot API helpers.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KEY_FILE = PROJECT_ROOT / "API_KEY" / "TELEGRAM_KEY"


class TelegramConfigError(RuntimeError):
    """Raised when Telegram credentials are not configured."""


class TelegramSendError(RuntimeError):
    """Raised when Telegram accepts the request as invalid or unreachable."""


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str
    chat_id: str


def load_telegram_config(
    *,
    dotenv_path: Path | None = PROJECT_ROOT / ".env",
    key_file: Path = DEFAULT_KEY_FILE,
) -> TelegramConfig:
    if dotenv_path and dotenv_path.exists():
        load_dotenv(dotenv_path, override=False)

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if key_file.exists():
        for line in key_file.read_text(encoding="utf-8").splitlines():
            key, value = _parse_key_value(line)
            if not key:
                continue
            if key in {"TELEGRAM_BOT_TOKEN", "BOT_TOKEN", "KEY"} and not token:
                token = value
            elif key in {"TELEGRAM_CHAT_ID", "CHAT_ID"} and not chat_id:
                chat_id = value

    if not token or not chat_id:
        raise TelegramConfigError("Telegram 설정 미완료 (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)")
    return TelegramConfig(bot_token=token, chat_id=chat_id)


def send_telegram_message(
    text: str,
    *,
    config: TelegramConfig | None = None,
    parse_mode: str | None = None,
    timeout: int = 15,
    requests_module: Any = requests,
) -> dict[str, Any]:
    cfg = config or load_telegram_config()
    payload: dict[str, Any] = {
        "chat_id": cfg.chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        response = requests_module.post(
            f"https://api.telegram.org/bot{cfg.bot_token}/sendMessage",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        raise TelegramSendError(mask_telegram_secret(str(exc), cfg)) from exc

    if not body.get("ok"):
        raise TelegramSendError(mask_telegram_secret(str(body), cfg))
    return body


def mask_telegram_secret(message: str, config: TelegramConfig | None) -> str:
    if not config:
        return message
    masked = message.replace(config.bot_token, "***")
    return masked.replace(config.chat_id, "***")


def _parse_key_value(line: str) -> tuple[str | None, str]:
    raw = line.strip()
    if not raw or raw.startswith("#") or "=" not in raw:
        return None, ""
    key, value = raw.split("=", 1)
    return key.strip(), value.strip()
