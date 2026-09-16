from __future__ import annotations

from pathlib import Path

from restic_backup.adapters.process import ProcessCommandError
from restic_backup.adapters.restic import ResticCliAdapter


class RunnerSpy:
    def __init__(self, capture_result: str = "[]", raise_on_capture: bool = False) -> None:
        self.calls: list[tuple[str, list[str], Path | None]] = []
        self._capture_result = capture_result
        self._raise_on_capture = raise_on_capture

    def run(self, args: list[str]) -> None:
        self.calls.append(("run", args, None))

    def run_in_dir(self, args: list[str], cwd: Path) -> None:
        self.calls.append(("run_in_dir", args, cwd))

    def run_capture(self, args: list[str]) -> str:
        self.calls.append(("run_capture", args, None))
        if self._raise_on_capture:
            raise ProcessCommandError(10, args, output="", stderr="Fatal: repository does not exist")
        return self._capture_result


def test_backup_runs_from_source_directory_to_restore_contents_without_nested_data_dir() -> None:
    runner = RunnerSpy()

    ResticCliAdapter(runner).backup(Path("/data"))

    assert runner.calls == [("run_in_dir", ["restic", "backup", "."], Path("/data"))]


def test_restore_targets_data_directory() -> None:
    runner = RunnerSpy()

    ResticCliAdapter(runner).restore(Path("/data"), before="2026-01-01T00:00:00Z")

    assert runner.calls == [
        ("run", ["restic", "restore", "latest", "--target", "/data", "--time", "2026-01-01T00:00:00Z"], None)
    ]


def test_has_snapshots_true_when_repository_has_snapshots() -> None:
    runner = RunnerSpy(capture_result='[{"id": "abc123"}]')

    assert ResticCliAdapter(runner).has_snapshots() is True
    assert runner.calls == [("run_capture", ["restic", "snapshots", "--json"], None)]


def test_has_snapshots_false_when_repository_is_empty() -> None:
    runner = RunnerSpy(capture_result="[]")

    assert ResticCliAdapter(runner).has_snapshots() is False


def test_has_snapshots_false_when_repository_was_never_initialized() -> None:
    runner = RunnerSpy(raise_on_capture=True)

    assert ResticCliAdapter(runner).has_snapshots() is False
