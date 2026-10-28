from __future__ import annotations

from pathlib import Path

from docuflow.config import Settings
from docuflow.storage.base import ObjectStorage
from docuflow.storage.filesystem import FilesystemStorage
from docuflow.storage.s3 import S3Storage


def build_storage(settings: Settings) -> ObjectStorage:
    if settings.storage_backend == "s3":
        return S3Storage(settings)
    return FilesystemStorage(Path(settings.storage_local_path))
