from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import IO

logger = logging.getLogger(__name__)


class ProcessRunner:
    def run(self, args: list[str], env: dict[str, str] | None = None) -> None:
        self._run(args, env=env)

    def run_in_dir(self, args: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
        self._run(args, env=env, cwd=cwd)

    def run_capture(self, args: list[str], env: dict[str, str] | None = None) -> str:
        return self._run(args, env=env).stdout

    def run_to_file(self, args: list[str], destination: Path, env: dict[str, str] | None = None) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8") as output:
            self._run(args, env=env, stdout=output)

    def run_from_file(self, args: list[str], source: Path, env: dict[str, str] | None = None) -> None:
        with source.open("r", encoding="utf-8") as input_file:
            self._run(args, env=env, stdin=input_file)

    def _run(
        self,
        args: list[str],
        env: dict[str, str] | None = None,
        stdin: IO[str] | None = None,
        stdout: IO[str] | int | None = subprocess.PIPE,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        log_args = self._redact(args)
        logger.info("Running command", extra={"command": log_args, "cwd": str(cwd) if cwd else None})
        completed = subprocess.run(
            args,
            env={**os.environ, **(env or {})},
            check=False,
            text=True,
            stdin=stdin,
            stdout=stdout,
            stderr=subprocess.PIPE,
            cwd=cwd,
        )
        if isinstance(completed.stdout, str) and completed.stdout:
            logger.debug("Command stdout", extra={"stdout": completed.stdout.strip()})
        if completed.stderr:
            logger.debug("Command stderr", extra={"stderr": completed.stderr.strip()})
        if completed.returncode != 0:
            raise subprocess.CalledProcessError(
                completed.returncode,
                log_args,
                output=completed.stdout,
                stderr=completed.stderr,
            )
        return completed

    def _redact(self, args: list[str]) -> list[str]:
        redacted: list[str] = []
        redact_next = False
        for arg in args:
            if redact_next:
                redacted.append("***")
                redact_next = False
                continue
            redacted.append(arg)
            if arg in {"--password", "-p"}:
                redact_next = True
        return redacted
