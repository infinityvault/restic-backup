from __future__ import annotations

from pathlib import Path

from restic_backup.application.use_cases import BackupUseCase, CleanupUseCase, RestoreUseCase


class ResticSpy:
    def __init__(self, has_snapshots: bool = True) -> None:
        self.calls: list[tuple[str, object]] = []
        self._has_snapshots = has_snapshots

    def backup(self, source: Path) -> None:
        self.calls.append(("backup", source))

    def restore(self, target: Path, before: str | None = None) -> None:
        self.calls.append(("restore", target, before))

    def forget(self, retention_args: list[str]) -> None:
        self.calls.append(("forget", retention_args))

    def prune(self) -> None:
        self.calls.append(("prune", None))

    def has_snapshots(self) -> bool:
        self.calls.append(("has_snapshots", None))
        return self._has_snapshots


class DatabaseSpy:
    def __init__(self, empty: bool = True) -> None:
        self.empty = empty
        self.calls: list[tuple[str, Path | None]] = []

    def dump(self, destination: Path) -> None:
        self.calls.append(("dump", destination))

    def is_empty(self) -> bool:
        self.calls.append(("is_empty", None))
        return self.empty

    def restore(self, source: Path) -> None:
        self.calls.append(("restore", source))


class FilesystemStub:
    def __init__(self, empty: bool, dump_exists: bool = True) -> None:
        self.empty = empty
        self.dump_exists = dump_exists

    def is_empty_dir(self, path: Path) -> bool:
        return self.empty

    def file_exists(self, path: Path) -> bool:
        return self.dump_exists


def test_backup_dumps_database_before_restic_backup(tmp_path: Path) -> None:
    restic = ResticSpy()
    database = DatabaseSpy()
    data_dir = tmp_path / "data"
    dump_path = data_dir / "database" / "dump.sql"

    BackupUseCase(restic, database).execute(data_dir, dump_path)

    assert database.calls == [("dump", dump_path)]
    assert restic.calls == [("backup", data_dir)]


def test_restore_restores_data_then_database_when_both_are_empty(tmp_path: Path) -> None:
    restic = ResticSpy(has_snapshots=True)
    database = DatabaseSpy(empty=True)
    data_dir = tmp_path / "data"
    dump_path = data_dir / "db_dump.sql"

    RestoreUseCase(restic, FilesystemStub(empty=True), database).execute(
        data_dir,
        dump_path,
        before="2026-01-01T00:00:00Z",
    )

    assert restic.calls == [("has_snapshots", None), ("restore", data_dir, "2026-01-01T00:00:00Z")]
    assert database.calls == [("is_empty", None), ("restore", dump_path)]


def test_restore_skips_restic_and_database_when_no_snapshots_exist(
    tmp_path: Path,
) -> None:
    restic = ResticSpy(has_snapshots=False)
    database = DatabaseSpy(empty=True)
    data_dir = tmp_path / "data"
    dump_path = data_dir / "db_dump.sql"

    RestoreUseCase(restic, FilesystemStub(empty=True, dump_exists=False), database).execute(
        data_dir, dump_path
    )

    assert restic.calls == [("has_snapshots", None)]
    assert not data_dir.exists()
    # No restic snapshot means the dump file (which lives inside data_dir)
    # was never restored either, so the database restore is skipped too -
    # without even checking is_empty(), since there's nothing to restore.
    assert database.calls == []


def test_restore_skips_database_restore_when_no_dump_file_is_present(tmp_path: Path) -> None:
    restic = ResticSpy(has_snapshots=True)
    database = DatabaseSpy(empty=True)
    data_dir = tmp_path / "data"
    dump_path = data_dir / "db_dump.sql"

    RestoreUseCase(restic, FilesystemStub(empty=True, dump_exists=False), database).execute(
        data_dir, dump_path
    )

    assert restic.calls == [("has_snapshots", None), ("restore", data_dir, None)]
    assert database.calls == []


def test_restore_skips_when_data_and_database_are_not_empty(tmp_path: Path) -> None:
    restic = ResticSpy()
    database = DatabaseSpy(empty=False)
    data_dir = tmp_path / "data"
    dump_path = data_dir / "db_dump.sql"

    RestoreUseCase(restic, FilesystemStub(empty=False), database).execute(data_dir, dump_path)

    # has_snapshots is only worth checking when a restore would otherwise
    # be attempted - the data directory being non-empty already skips it.
    assert restic.calls == []
    assert database.calls == [("is_empty", None)]


def test_cleanup_forgets_then_prunes() -> None:
    restic = ResticSpy()

    CleanupUseCase(restic).execute(["--keep-weekly", "2"])

    assert restic.calls == [("forget", ["--keep-weekly", "2"]), ("prune", None)]
