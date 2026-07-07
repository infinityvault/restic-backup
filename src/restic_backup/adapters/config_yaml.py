from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Any, Mapping

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
    def load(self, path: Path, env: Mapping[str, str] | None = None) -> AppConfig:
        raw = self._load_yaml(path)
        raw = self._with_environment(raw, os.environ if env is None else env)

        database = self._database(raw.get("database"))
        notifications = self._notifications(raw.get("notifications"))

        return AppConfig(
            data_dir=Path(raw.get("data_dir", "/data")),
            db_dump_file=Path(raw.get("db_dump_file", "db_dump.sql")),
            database=database,
            notifications=notifications,
        )

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}

        with path.open("r", encoding="utf-8") as config_file:
            return yaml.safe_load(config_file) or {}

    def _with_environment(self, raw: dict[str, Any], env: Mapping[str, str]) -> dict[str, Any]:
        merged = dict(raw)

        _set_if_present(merged, "data_dir", env, "RESTIC_BACKUP_DATA_DIR")
        _set_if_present(merged, "db_dump_file", env, "RESTIC_BACKUP_DB_DUMP_FILE")

        database = dict(merged.get("database") or {})
        _set_if_present(database, "type", env, "RESTIC_BACKUP_DATABASE_TYPE")
        _set_if_present(database, "host", env, "RESTIC_BACKUP_DATABASE_HOST")
        _set_if_present(database, "port", env, "RESTIC_BACKUP_DATABASE_PORT", int)
        _set_if_present(database, "username", env, "RESTIC_BACKUP_DATABASE_USERNAME")
        _set_if_present(database, "password", env, "RESTIC_BACKUP_DATABASE_PASSWORD")
        _set_if_present(database, "database", env, "RESTIC_BACKUP_DATABASE_NAME")
        _set_if_present(database, "extra_args", env, "RESTIC_BACKUP_DATABASE_EXTRA_ARGS", shlex.split)
        if database:
            merged["database"] = database

        notifications = dict(merged.get("notifications") or {})
        _set_if_present(notifications, "mode", env, "RESTIC_BACKUP_NOTIFICATIONS_MODE")

        telegram = dict(notifications.get("telegram") or {})
        _set_if_present(telegram, "bot_token", env, "RESTIC_BACKUP_TELEGRAM_BOT_TOKEN")
        _set_if_present(telegram, "chat_id", env, "RESTIC_BACKUP_TELEGRAM_CHAT_ID")
        if telegram:
            notifications["telegram"] = telegram
        if notifications:
            merged["notifications"] = notifications

        return merged

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


def _set_if_present(
    target: dict[str, Any],
    target_key: str,
    env: Mapping[str, str],
    env_key: str,
    convert: Any = str,
) -> None:
    value = env.get(env_key)
    if value is not None:
        target[target_key] = convert(value)
