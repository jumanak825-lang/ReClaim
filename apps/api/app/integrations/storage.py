"""Storage adapter (CLAUDE.md: keep provider access behind an adapter).

Only the local-disk provider exists for the hackathon (docs/11). An S3/Cloudinary/Supabase
provider implements the same three methods.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Protocol

from ..core import config

_KEY = re.compile(r"^[A-Za-z0-9_-]{1,100}$")


class Storage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def clear_all(self) -> None: ...


class LocalDiskStorage:
    def __init__(self, root: Path):
        self.root = root

    def _path(self, key: str) -> Path:
        if not _KEY.match(key):  # keys are server-generated; refuse anything path-like
            raise ValueError("invalid storage key")
        return self.root / key

    def put(self, key: str, data: bytes) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._path(key).write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def clear_all(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)


def storage() -> Storage:
    s = config.settings
    if s.upload_provider != "local":
        raise RuntimeError(f"UPLOAD_PROVIDER={s.upload_provider} is not implemented yet; use 'local'.")
    return LocalDiskStorage(s.upload_dir)
