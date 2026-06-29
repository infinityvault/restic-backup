from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class DatabaseType(StrEnum):
    POSTGRES = "postgres"
    MYSQL = "mysql"


class NotificationMode(StrEnum):
    ALWAYS = "always"
    ON_FAILURE = "on_failure"


@dataclass(frozen=True)
class DatabaseConfig:
    type: DatabaseType
    host: str = "localhost"
    port: int | None = None
    username: str | None = None
    password: str | None = None
    database: str | None = None
    extra_args: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str
    chat_id: str


@dataclass(frozen=True)
class NotificationsConfig:
    mode: NotificationMode = NotificationMode.ON_FAILURE
    telegram: TelegramConfig | None = None


@dataclass(frozen=True)
class AppConfig:
    data_dir: Path = Path("/data")
    db_dump_file: Path = Path("db_dump.sql")
    database: DatabaseConfig | None = None
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)

    @property
    def db_dump_path(self) -> Path:
        return self.data_dir / self.db_dump_file
