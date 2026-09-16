from __future__ import annotations

from pathlib import Path
from typing import Protocol

from restic_backup.domain.models import AppConfig


class ConfigPort(Protocol):
    def load(self, path: Path) -> AppConfig:
        """Load application configuration."""


class DatabasePort(Protocol):
    def dump(self, destination: Path) -> None:
        """Dump the configured database to destination."""

    def is_empty(self) -> bool:
        """Return whether the configured database has no user data."""

    def restore(self, source: Path) -> None:
        """Restore the configured database from source."""


class ResticPort(Protocol):
    def backup(self, source: Path) -> None:
        """Create a restic snapshot from source."""

    def restore(self, target: Path, before: str | None = None) -> None:
        """Restore the latest snapshot, optionally before a point in time."""

    def forget(self, retention_args: list[str]) -> None:
        """Run restic forget with retention args."""

    def prune(self) -> None:
        """Run restic prune."""


class FileSystemPort(Protocol):
    def is_empty_dir(self, path: Path) -> bool:
        """Return whether path is missing or contains no entries."""


class NotifierPort(Protocol):
    def notify(self, title: str, message: str, success: bool) -> None:
        """Send a notification."""
