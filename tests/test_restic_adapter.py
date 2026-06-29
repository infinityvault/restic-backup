from __future__ import annotations

from pathlib import Path

from restic_backup.adapters.restic import ResticCliAdapter


class RunnerSpy:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str], Path | None]] = []

    def run(self, args: list[str]) -> None:
        self.calls.append(("run", args, None))

    def run_in_dir(self, args: list[str], cwd: Path) -> None:
        self.calls.append(("run_in_dir", args, cwd))


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
