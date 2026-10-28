from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from docuflow.config import Settings
from docuflow.exceptions import AuthorizationError, FileTooLargeError, NotFoundError
from docuflow.models import Document, User
from docuflow.pdf.engine import PdfEngine
from docuflow.pdf.sniff import sniff_file
from docuflow.storage.base import ObjectStorage


class DocumentService:
    def __init__(self, session: Session, storage: ObjectStorage, settings: Settings) -> None:
        self.session = session
        self.storage = storage
        self.settings = settings
        self.engine = PdfEngine(max_bytes=settings.max_upload_bytes, max_pages=settings.max_pages)

    def store_upload(self, user: User, source: Path, original_filename: str) -> Document:
        return self._store(
            user, source, original_filename, origin="upload", retention_hours=self.settings.file_retention_hours
        )

    def store_result(self, user: User, source: Path, original_filename: str, origin: str) -> Document:
        return self._store(
            user, source, original_filename, origin=origin, retention_hours=self.settings.result_retention_hours
        )

    def get_owned(self, user: User, document_id: str) -> Document:
        document = self.session.get(Document, document_id)
        if document is None or document.deleted_at is not None:
            raise NotFoundError("Document not found.")
        if document.user_id != user.id and user.role != "admin":
            raise AuthorizationError("You cannot access this document.")
        return document

    def list_for_user(self, user: User) -> list[Document]:
        rows = self.session.scalars(
            select(Document)
            .where(Document.user_id == user.id, Document.deleted_at.is_(None))
            .order_by(Document.created_at.desc())
        )
        return list(rows)

    def delete(self, user: User, document_id: str) -> None:
        document = self.get_owned(user, document_id)
        self.storage.delete(document.storage_key)
        document.deleted_at = datetime.now(UTC)
        self.session.commit()

    def purge_expired(self) -> int:
        now = datetime.now(UTC)
        rows = list(
            self.session.scalars(select(Document).where(Document.deleted_at.is_(None), Document.expires_at < now))
        )
        for document in rows:
            self.storage.delete(document.storage_key)
            document.deleted_at = now
        self.session.commit()
        return len(rows)

    def _store(
        self,
        user: User,
        source: Path,
        original_filename: str,
        *,
        origin: str,
        retention_hours: int,
    ) -> Document:
        if source.stat().st_size > self.settings.max_upload_bytes:
            raise FileTooLargeError("File exceeds the configured upload limit.")
        kind = sniff_file(source)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        key = f"{user.id}/{uuid.uuid4().hex}{kind.extension}"
        self.storage.put(key, source, kind.mime)
        page_count = None
        if kind.kind == "pdf":
            try:
                page_count = self.engine.inspect(source).page_count
            except Exception:
                page_count = None
        document = Document(
            user_id=user.id,
            original_filename=Path(original_filename).name[:255] or f"file{kind.extension}",
            content_type=kind.mime,
            kind=kind.kind,
            byte_size=source.stat().st_size,
            page_count=page_count,
            storage_key=key,
            sha256=digest,
            origin=origin,
            expires_at=datetime.now(UTC) + timedelta(hours=retention_hours),
        )
        self.session.add(document)
        self.session.commit()
        self.session.refresh(document)
        return document
