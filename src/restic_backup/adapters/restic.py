from __future__ import annotations

from pathlib import Path

from restic_backup.adapters.process import ProcessCommandError, ProcessRunner


class ResticCliAdapter:
    def __init__(self, runner: ProcessRunner) -> None:
        self._runner = runner

    def backup(self, source: Path) -> None:
        self._ensure_initialized()
        self._runner.run_in_dir(["restic", "backup", "."], cwd=source)

    def restore(self, target: Path, before: str | None = None) -> None:
        self._ensure_initialized()
        args = ["restic", "restore", "latest", "--target", str(target)]
        if before:
            args.extend(["--time", before])
        self._runner.run(args)

    def forget(self, retention_args: list[str]) -> None:
        self._ensure_initialized()
        self._runner.run(["restic", "forget", *retention_args])

    def prune(self) -> None:
        self._ensure_initialized()
        self._runner.run(["restic", "prune"])

    def _ensure_initialized(self) -> None:
        # `restic cat config` fails whenever the repository hasn't been
        # created yet - initialize it on demand so backup/restore/forget/
        # prune never have to assume it already exists. If it's already
        # initialized this is a no-op; if init itself fails (e.g. bad
        # credentials), that failure propagates normally.
        try:
            self._runner.run(["restic", "cat", "config"])
        except ProcessCommandError:
            self._runner.run(["restic", "init"])
