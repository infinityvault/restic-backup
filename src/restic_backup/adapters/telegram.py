from __future__ import annotations

import logging

import requests

from restic_backup.domain.models import TelegramConfig

logger = logging.getLogger(__name__)


class TelegramNotifierAdapter:
    def __init__(self, config: TelegramConfig) -> None:
        self._config = config

    def notify(self, title: str, message: str, success: bool) -> None:
        status = "SUCCESS" if success else "FAILURE"
        text = f"{title}: {status}\n{message}"
        url = f"https://api.telegram.org/bot{self._config.bot_token}/sendMessage"
        logger.info("Sending Telegram notification", extra={"chat_id": self._config.chat_id, "success": success})
        response = requests.post(
            url,
            json={"chat_id": self._config.chat_id, "text": text},
            timeout=10,
        )
        response.raise_for_status()
