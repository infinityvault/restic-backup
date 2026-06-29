from __future__ import annotations

import logging
from pathlib import Path

from restic_backup.domain.ports import DatabasePort, FileSystemPort, ResticPort

logger = logging.getLogger(__name__)


class BackupUseCase:
    def __init__(self, restic: ResticPort, database: DatabasePort | None) -> None:
        self._restic = restic
        self._database = database

    def execute(self, data_dir: Path, db_dump_path: Path) -> None:
        if self._database:
            logger.info("Creating database dump", extra={"destination": str(db_dump_path)})
            db_dump_path.parent.mkdir(parents=True, exist_ok=True)
            self._database.dump(db_dump_path)

        logger.info("Creating restic snapshot", extra={"source": str(data_dir)})
        self._restic.backup(data_dir)


class RestoreUseCase:
    def __init__(
        self,
        restic: ResticPort,
        filesystem: FileSystemPort,
        database: DatabasePort | None,
    ) -> None:
        self._restic = restic
        self._filesystem = filesystem
        self._database = database

    def execute(self, data_dir: Path, db_dump_path: Path, before: str | None = None) -> None:
        if self._filesystem.is_empty_dir(data_dir):
            logger.info("Restoring data from restic", extra={"target": str(data_dir), "before": before})
            data_dir.mkdir(parents=True, exist_ok=True)
            self._restic.restore(data_dir, before=before)
        else:
            logger.info("Skipping restic restore because data directory is not empty", extra={"target": str(data_dir)})

        if not self._database:
            return

        if self._database.is_empty():
            logger.info("Restoring database dump", extra={"source": str(db_dump_path)})
            self._database.restore(db_dump_path)
        else:
            logger.info("Skipping database restore because database is not empty")


class CleanupUseCase:
    def __init__(self, restic: ResticPort) -> None:
        self._restic = restic

    def execute(self, retention_args: list[str]) -> None:
        logger.info("Forgetting restic snapshots", extra={"retention_args": retention_args})
        self._restic.forget(retention_args)
        logger.info("Pruning restic repository")
        self._restic.prune()
