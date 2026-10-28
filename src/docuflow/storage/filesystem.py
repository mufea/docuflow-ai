from __future__ import annotations

import shutil
from pathlib import Path

from docuflow.exceptions import NotFoundError
from docuflow.storage.base import StoredObject


class FilesystemStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        if ".." in Path(key).parts or Path(key).is_absolute():
            raise ValueError("Invalid storage key.")
        path = (self.root / key).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise ValueError("Storage key escapes the storage root.")
        return path

    def put(self, key: str, source: Path, content_type: str) -> StoredObject:
        dest = self._path_for(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        return StoredObject(key=key, content_type=content_type, byte_size=dest.stat().st_size)

    def download(self, key: str, dest: Path) -> Path:
        source = self._path_for(key)
        if not source.is_file():
            raise NotFoundError("Stored object was not found.")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        return dest

    def delete(self, key: str) -> None:
        path = self._path_for(key)
        if path.is_file():
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._path_for(key).is_file()

    def signed_url(self, key: str, *, expires_seconds: int, filename: str | None = None) -> str | None:
        return None
