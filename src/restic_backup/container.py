from __future__ import annotations

from restic_backup.adapters.database import create_database_adapter
from restic_backup.adapters.filesystem import LocalFileSystemAdapter
from restic_backup.adapters.process import ProcessRunner
from restic_backup.adapters.restic import ResticCliAdapter
from restic_backup.adapters.telegram import TelegramNotifierAdapter
from restic_backup.domain.models import AppConfig
from restic_backup.domain.ports import DatabasePort, NotifierPort


class Container:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.runner = ProcessRunner()
        self.restic = ResticCliAdapter(self.runner)
        self.filesystem = LocalFileSystemAdapter()
        self.database = self._database()
        self.notifier = self._notifier()

    def _database(self) -> DatabasePort | None:
        if not self.config.database:
            return None
        return create_database_adapter(self.config.database, self.runner)

    def _notifier(self) -> NotifierPort | None:
        telegram = self.config.notifications.telegram
        if not telegram:
            return None
        return TelegramNotifierAdapter(telegram)
