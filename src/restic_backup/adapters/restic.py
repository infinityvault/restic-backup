from __future__ import annotations

import json
from pathlib import Path

from restic_backup.adapters.process import ProcessCommandError, ProcessRunner


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

    def has_snapshots(self) -> bool:
        # A repository that was never `restic init`'d fails this command
        # the same way an initialized-but-empty one succeeds with `[]` -
        # both mean "nothing to restore yet" to the caller.
        try:
            output = self._runner.run_capture(["restic", "snapshots", "--json"])
        except ProcessCommandError:
            return False
        return bool(json.loads(output))

    def forget(self, retention_args: list[str]) -> None:
        self._runner.run(["restic", "forget", *retention_args])

    def prune(self) -> None:
        self._runner.run(["restic", "prune"])
