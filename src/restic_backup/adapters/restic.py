from __future__ import annotations

from pathlib import Path

from restic_backup.adapters.process import ProcessRunner


class ResticCliAdapter:
    def __init__(self, runner: ProcessRunner) -> None:
        self._runner = runner

    def backup(self, source: Path) -> None:
        self._runner.run_in_dir(["restic", "backup", "."], cwd=source)

    def restore(self, target: Path, before: str | None = None) -> None:
        args = ["restic", "restore", "latest", "--target", str(target)]
        if before:
            args.extend(["--time", before])
        self._runner.run(args)

    def forget(self, retention_args: list[str]) -> None:
        self._runner.run(["restic", "forget", *retention_args])

    def prune(self) -> None:
        self._runner.run(["restic", "prune"])
