from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from docuflow.config import Settings
from docuflow.exceptions import AuthorizationError, FileTooLargeError, NotFoundError, TransientError
from docuflow.jobs.clock import utc_now
from docuflow.models import Document, StorageDeletion, User
from docuflow.pdf.engine import PdfEngine
from docuflow.pdf.sniff import sniff_file
from docuflow.storage.base import ObjectStorage

logger = logging.getLogger("docuflow.documents")


def deletion_backoff_minutes(attempt: int) -> int:
    return min(60, 2 ** max(attempt - 1, 0))


def _format_storage_error(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}".strip()
    return text[:80]


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

    def purge_expired(self, heartbeat: Callable[[], bool] | None = None) -> int:
        now = datetime.now(UTC)
        rows = list(
            self.session.scalars(select(Document).where(Document.deleted_at.is_(None), Document.expires_at < now))
        )
        marked = 0
        for document in rows:
            if heartbeat is not None and not heartbeat():
                break
            document.deleted_at = now
            self._enqueue_deletion(document.id, document.storage_key)
            marked += 1
        self.session.commit()
        return marked

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

    def retry_storage_deletions(
        self,
        *,
        limit: int = 50,
        document_id: str | None = None,
        heartbeat: Callable[[], bool] | None = None,
    ) -> dict[str, int]:
        now = utc_now()
        lease_minutes = max(1, int(self.settings.storage_delete_lease_minutes))
        owner_token = uuid.uuid4().hex
        self._expire_stuck_deletions(now)
        due = self._due_deletion_rows(now, limit=limit, document_id=document_id)
        deleted = 0
        failures = 0
        retries = 0
        for row in due:
            if heartbeat is not None and not heartbeat():
                break
            if not self._claim_deletion(row.id, owner_token=owner_token, lease_minutes=lease_minutes):
                continue
            current = self.session.get(StorageDeletion, row.id)
            if current is None:
                continue
            deletion_id = current.id
            storage_key = current.storage_key
            attempts = current.attempts
            max_attempts = current.max_attempts
            self.session.expire(current)
            retries += 1
            if not self._renew_deletion_lease(deletion_id, owner_token, lease_minutes):
                logger.warning("storage_delete_lost_ownership id=%s stage=renew", deletion_id)
                continue
            try:
                self._delete_object_idempotent(storage_key)
            except Exception as exc:
                if self._finish_owned_deletion(
                    deletion_id,
                    owner_token,
                    attempts=attempts,
                    max_attempts=max_attempts,
                    error=_format_storage_error(exc),
                ):
                    failures += 1
                else:
                    logger.warning("storage_delete_lost_ownership id=%s stage=fail", deletion_id)
                continue
            if self._finish_owned_deletion(deletion_id, owner_token, success=True):
                deleted += 1
            else:
                logger.warning("storage_delete_lost_ownership id=%s stage=complete", deletion_id)
        return {"deleted": deleted, "failures": failures, "retries": retries}

    def _due_deletion_rows(self, now: datetime, *, limit: int, document_id: str | None) -> list[StorageDeletion]:
        query = (
            select(StorageDeletion)
            .where(
                StorageDeletion.status.in_(("pending", "failed", "in_progress")),
                StorageDeletion.attempts < StorageDeletion.max_attempts,
                or_(
                    and_(
                        StorageDeletion.status.in_(("pending", "failed")),
                        StorageDeletion.next_attempt_at <= now,
                    ),
                    and_(
                        StorageDeletion.status == "in_progress",
                        or_(StorageDeletion.lease_until.is_(None), StorageDeletion.lease_until < now),
                    ),
                ),
            )
            .order_by(StorageDeletion.next_attempt_at.asc())
            .limit(limit)
        )
        if document_id:
            query = query.where(StorageDeletion.document_id == document_id)
        return list(self.session.scalars(query))

    def _claim_deletion(self, deletion_id: str, *, owner_token: str, lease_minutes: int) -> bool:
        now = utc_now()
        claimed = self.session.execute(
            update(StorageDeletion)
            .where(
                StorageDeletion.id == deletion_id,
                StorageDeletion.status.in_(("pending", "failed", "in_progress")),
                or_(
                    StorageDeletion.status.in_(("pending", "failed")),
                    StorageDeletion.lease_until.is_(None),
                    StorageDeletion.lease_until < now,
                ),
            )
            .values(
                status="in_progress",
                attempts=StorageDeletion.attempts + 1,
                started_at=now,
                lease_until=now + timedelta(minutes=lease_minutes),
                owner_token=owner_token,
            )
            .execution_options(synchronize_session=False)
        )
        self.session.commit()
        won = int(getattr(claimed, "rowcount", 0) or 0) == 1
        self._expire_deletion(deletion_id)
        return won

    def _renew_deletion_lease(self, deletion_id: str, owner_token: str, lease_minutes: int) -> bool:
        now = utc_now()
        renewed = self.session.execute(
            update(StorageDeletion)
            .where(
                StorageDeletion.id == deletion_id,
                StorageDeletion.status == "in_progress",
                StorageDeletion.owner_token == owner_token,
            )
            .values(lease_until=now + timedelta(minutes=lease_minutes))
            .execution_options(synchronize_session=False)
        )
        self.session.commit()
        won = int(getattr(renewed, "rowcount", 0) or 0) == 1
        self._expire_deletion(deletion_id)
        return won

    def _finish_owned_deletion(
        self,
        deletion_id: str,
        owner_token: str,
        *,
        success: bool = False,
        attempts: int = 0,
        max_attempts: int = 0,
        error: str | None = None,
    ) -> bool:
        now = utc_now()
        if success:
            values: dict[str, object] = {
                "status": "completed",
                "completed_at": now,
                "last_error": None,
                "lease_until": None,
                "owner_token": None,
            }
        elif attempts >= max_attempts:
            values = {
                "status": "exhausted",
                "last_error": error,
                "lease_until": None,
                "owner_token": None,
            }
            logger.warning("storage_delete_exhausted attempts=%s error=%s", attempts, error)
        else:
            delay = deletion_backoff_minutes(attempts)
            values = {
                "status": "failed",
                "last_error": error,
                "lease_until": None,
                "owner_token": None,
                "next_attempt_at": now + timedelta(minutes=delay),
            }
            logger.warning("storage_delete_retry attempts=%s backoff_min=%s error=%s", attempts, delay, error)
        finished = self.session.execute(
            update(StorageDeletion)
            .where(
                StorageDeletion.id == deletion_id,
                StorageDeletion.status == "in_progress",
                StorageDeletion.owner_token == owner_token,
            )
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        self.session.commit()
        won = int(getattr(finished, "rowcount", 0) or 0) == 1
        self._expire_deletion(deletion_id)
        return won

    def _expire_deletion(self, deletion_id: str) -> None:
        current = self.session.get(StorageDeletion, deletion_id)
        if current is not None:
            self.session.expire(current)

    def _expire_stuck_deletions(self, now: datetime) -> None:
        stuck = self.session.execute(
            update(StorageDeletion)
            .where(
                StorageDeletion.status == "in_progress",
                StorageDeletion.attempts >= StorageDeletion.max_attempts,
                or_(StorageDeletion.lease_until.is_(None), StorageDeletion.lease_until < now),
            )
            .values(status="exhausted", lease_until=None, owner_token=None)
            .execution_options(synchronize_session=False)
        )
        expired_count = int(getattr(stuck, "rowcount", 0) or 0)
        if expired_count:
            logger.warning("storage_delete_expired_exhausted count=%s", expired_count)
            self.session.commit()
        self.session.expire_all()

    def _delete_object_idempotent(self, storage_key: str) -> None:
        try:
            self.storage.delete(storage_key)
        except NotFoundError:
            return
        except TransientError:
            raise
        if self.storage.exists(storage_key):
            raise RuntimeError("ObjectStillPresent")

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
