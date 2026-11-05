from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from docuflow.config import Settings
from docuflow.exceptions import AuthorizationError, FileTooLargeError, NotFoundError
from docuflow.models import Document, StorageDeletion, User
from docuflow.pdf.engine import PdfEngine
from docuflow.pdf.sniff import sniff_file
from docuflow.storage.base import ObjectStorage

logger = logging.getLogger("docuflow.documents")


def deletion_backoff_minutes(attempt: int) -> int:
    return min(60, 2 ** max(attempt - 1, 0))


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
        now = datetime.now(UTC)
        document.deleted_at = now
        self._enqueue_deletion(document.id, document.storage_key)
        self.session.commit()
        self.retry_storage_deletions(limit=1, document_id=document.id)

    def purge_expired(self) -> int:
        now = datetime.now(UTC)
        rows = list(
            self.session.scalars(select(Document).where(Document.deleted_at.is_(None), Document.expires_at < now))
        )
        for document in rows:
            document.deleted_at = now
            self._enqueue_deletion(document.id, document.storage_key)
        self.session.commit()
        return len(rows)

    def _enqueue_deletion(self, document_id: str, storage_key: str) -> StorageDeletion:
        existing = self.session.scalar(select(StorageDeletion).where(StorageDeletion.storage_key == storage_key))
        if existing:
            if existing.status == "completed":
                return existing
            existing.document_id = existing.document_id or document_id
            if existing.status == "exhausted":
                existing.attempts = 0
            existing.status = "pending"
            existing.next_attempt_at = datetime.now(UTC)
            existing.last_error = None
            return existing
        row = StorageDeletion(
            document_id=document_id,
            storage_key=storage_key,
            status="pending",
            max_attempts=self.settings.storage_delete_max_attempts,
            next_attempt_at=datetime.now(UTC),
        )
        self.session.add(row)
        self.session.flush()
        return row

    def retry_storage_deletions(self, *, limit: int = 50, document_id: str | None = None) -> dict[str, int]:
        now = datetime.now(UTC)
        query = (
            select(StorageDeletion)
            .where(
                StorageDeletion.status.in_(("pending", "failed")),
                StorageDeletion.next_attempt_at <= now,
                StorageDeletion.attempts < StorageDeletion.max_attempts,
            )
            .order_by(StorageDeletion.next_attempt_at.asc())
            .limit(limit)
        )
        if document_id:
            query = query.where(StorageDeletion.document_id == document_id)
        due = list(self.session.scalars(query))
        deleted = 0
        failures = 0
        retries = 0
        for row in due:
            claimed = self.session.execute(
                update(StorageDeletion)
                .where(
                    StorageDeletion.id == row.id,
                    StorageDeletion.status.in_(("pending", "failed")),
                )
                .values(status="in_progress", attempts=StorageDeletion.attempts + 1)
            )
            self.session.commit()
            if int(getattr(claimed, "rowcount", 0) or 0) != 1:
                continue
            current = self.session.get(StorageDeletion, row.id)
            if current is None:
                continue
            retries += 1
            try:
                self.storage.delete(current.storage_key)
                if self.storage.exists(current.storage_key):
                    raise RuntimeError("ObjectStillPresent")
                current.status = "completed"
                current.completed_at = datetime.now(UTC)
                current.last_error = None
                deleted += 1
            except Exception as exc:
                failures += 1
                current.last_error = type(exc).__name__[:80]
                if current.attempts >= current.max_attempts:
                    current.status = "exhausted"
                    logger.warning(
                        "storage_delete_exhausted attempts=%s error=%s",
                        current.attempts,
                        current.last_error,
                    )
                else:
                    delay = deletion_backoff_minutes(current.attempts)
                    current.status = "failed"
                    current.next_attempt_at = datetime.now(UTC) + timedelta(minutes=delay)
                    logger.warning(
                        "storage_delete_retry attempts=%s backoff_min=%s error=%s",
                        current.attempts,
                        delay,
                        current.last_error,
                    )
            self.session.commit()
        return {"deleted": deleted, "failures": failures, "retries": retries}

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
