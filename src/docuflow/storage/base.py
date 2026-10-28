from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class StoredObject:
    key: str
    content_type: str
    byte_size: int


class ObjectStorage(Protocol):
    def put(self, key: str, source: Path, content_type: str) -> StoredObject: ...

    def download(self, key: str, dest: Path) -> Path: ...

    def delete(self, key: str) -> None: ...

    def exists(self, key: str) -> bool: ...

    def signed_url(self, key: str, *, expires_seconds: int, filename: str | None = None) -> str | None: ...
