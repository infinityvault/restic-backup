from __future__ import annotations

from pathlib import Path

from restic_backup.adapters.process import ProcessCommandError
from restic_backup.adapters.restic import ResticCliAdapter

_CAT_CONFIG = ["restic", "cat", "config"]
_INIT = ["restic", "init"]


class RunnerSpy:
    def __init__(self, fail_commands: list[list[str]] | None = None) -> None:
        self.calls: list[tuple[str, list[str], Path | None]] = []
        self._fail_commands = fail_commands or []

    def run(self, args: list[str]) -> None:
        self.calls.append(("run", args, None))
        if args in self._fail_commands:
            raise ProcessCommandError(1, args, output="", stderr="boom")

    def run_in_dir(self, args: list[str], cwd: Path) -> None:
        self.calls.append(("run_in_dir", args, cwd))


def test_backup_runs_from_source_directory_to_restore_contents_without_nested_data_dir() -> None:
    runner = RunnerSpy()

    ResticCliAdapter(runner).backup(Path("/data"))

    assert runner.calls == [
        ("run", _CAT_CONFIG, None),
        ("run_in_dir", ["restic", "backup", "."], Path("/data")),
    ]


def test_restore_targets_data_directory() -> None:
    runner = RunnerSpy()

    ResticCliAdapter(runner).restore(Path("/data"), before="2026-01-01T00:00:00Z")

    assert runner.calls == [
        ("run", _CAT_CONFIG, None),
        ("run", ["restic", "restore", "latest", "--target", "/data", "--time", "2026-01-01T00:00:00Z"], None),
    ]


def test_forget_ensures_repository_is_initialized() -> None:
    runner = RunnerSpy()

    ResticCliAdapter(runner).forget(["--keep-daily", "7"])

    assert runner.calls == [
        ("run", _CAT_CONFIG, None),
        ("run", ["restic", "forget", "--keep-daily", "7"], None),
    ]


def test_prune_ensures_repository_is_initialized() -> None:
    runner = RunnerSpy()

    ResticCliAdapter(runner).prune()

    assert runner.calls == [
        ("run", _CAT_CONFIG, None),
        ("run", ["restic", "prune"], None),
    ]


def test_ensure_initialized_initializes_repository_when_not_already_initialized() -> None:
    runner = RunnerSpy(fail_commands=[_CAT_CONFIG])

    ResticCliAdapter(runner).backup(Path("/data"))

    assert runner.calls == [
        ("run", _CAT_CONFIG, None),
        ("run", _INIT, None),
        ("run_in_dir", ["restic", "backup", "."], Path("/data")),
    ]


def test_ensure_initialized_does_not_reinitialize_an_existing_repository() -> None:
    runner = RunnerSpy()

    ResticCliAdapter(runner).restore(Path("/data"))

    assert runner.calls == [
        ("run", _CAT_CONFIG, None),
        ("run", ["restic", "restore", "latest", "--target", "/data"], None),
    ]
    assert _INIT not in [call[1] for call in runner.calls]
