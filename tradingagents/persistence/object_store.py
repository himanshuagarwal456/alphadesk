"""Local filesystem object storage for documents and raw artifacts.

Phase 3 keeps the interface small so an S3-compatible backend can replace the
local store later without changing repositories or the API.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class StoredObject:
    key: str
    path: Path
    content_hash: str
    size_bytes: int
    content_type: str


class ObjectStore(Protocol):
    def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> StoredObject: ...

    def get(self, key: str) -> bytes | None: ...

    def delete(self, key: str) -> bool: ...

    def exists(self, key: str) -> bool: ...


class LocalObjectStore:
    """Workspace-scoped keys under a root directory (atomic writes)."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        # Reject path traversal while allowing nested keys like "ws/a/b.json".
        normalized = Path(key.replace("\\", "/"))
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError(f"invalid object key: {key!r}")
        return self.root / normalized

    def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> StoredObject:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(data).hexdigest()
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(data)
        os.replace(temporary, path)
        return StoredObject(
            key=key,
            path=path,
            content_hash=digest,
            size_bytes=len(data),
            content_type=content_type,
        )

    def get(self, key: str) -> bytes | None:
        path = self._path_for(key)
        if not path.exists():
            return None
        return path.read_bytes()

    def delete(self, key: str) -> bool:
        path = self._path_for(key)
        if not path.exists():
            return False
        path.unlink()
        return True

    def exists(self, key: str) -> bool:
        return self._path_for(key).exists()
