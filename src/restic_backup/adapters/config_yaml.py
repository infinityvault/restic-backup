from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from restic_backup.domain.models import (
    AppConfig,
    DatabaseConfig,
    DatabaseType,
    NotificationMode,
    NotificationsConfig,
    TelegramConfig,
)


class YamlConfigAdapter:
    def load(self, path: Path) -> AppConfig:
        with path.open("r", encoding="utf-8") as config_file:
            raw = yaml.safe_load(config_file) or {}

        database = self._database(raw.get("database"))
        notifications = self._notifications(raw.get("notifications"))

        return AppConfig(
            data_dir=Path(raw.get("data_dir", "/data")),
            db_dump_file=Path(raw.get("db_dump_file", "db_dump.sql")),
            database=database,
            notifications=notifications,
        )

    def _database(self, raw: dict[str, Any] | None) -> DatabaseConfig | None:
        if not raw:
            return None

        return DatabaseConfig(
            type=DatabaseType(raw["type"]),
            host=raw.get("host", "localhost"),
            port=raw.get("port"),
            username=raw.get("username"),
            password=raw.get("password"),
            database=raw.get("database"),
            extra_args=tuple(raw.get("extra_args", ())),
        )

    def _notifications(self, raw: dict[str, Any] | None) -> NotificationsConfig:
        if not raw:
            return NotificationsConfig()

        telegram = raw.get("telegram")
        return NotificationsConfig(
            mode=NotificationMode(raw.get("mode", NotificationMode.ON_FAILURE.value)),
            telegram=TelegramConfig(
                bot_token=telegram["bot_token"],
                chat_id=str(telegram["chat_id"]),
            )
            if telegram
            else None,
        )
