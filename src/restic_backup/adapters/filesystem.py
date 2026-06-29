from __future__ import annotations

from pathlib import Path


class LocalFileSystemAdapter:
    def is_empty_dir(self, path: Path) -> bool:
        if not path.exists():
            return True
        if not path.is_dir():
            raise NotADirectoryError(path)
        return next(path.iterdir(), None) is None
