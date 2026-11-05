from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select, text, update
from sqlalchemy.orm import Session

from docuflow.billing.ledger import CreditService
from docuflow.config import Settings
from docuflow.models import CleanupLease, Job, User
from docuflow.services.documents import DocumentService
from docuflow.storage.base import ObjectStorage

logger = logging.getLogger("docuflow.cleanup")

CLEANUP_LOCK_KEY = 86420139
LEASE_NAME = "runtime"
LEASE_MINUTES = 5


@dataclass
class CleanupStats:
    abandoned_jobs: int = 0
    refunded_credits: int = 0
    expired_documents: int = 0
    storage_deleted: int = 0
    storage_failures: int = 0
    storage_retries: int = 0
    duration_ms: int = 0
    skipped: bool = False

    def as_log_fields(self) -> dict[str, int | bool]:
        return {
            "abandoned_jobs": self.abandoned_jobs,
            "refunded_credits": self.refunded_credits,
            "expired_documents": self.expired_documents,
            "storage_deleted": self.storage_deleted,
            "storage_failures": self.storage_failures,
            "storage_retries": self.storage_retries,
            "duration_ms": self.duration_ms,
            "skipped": self.skipped,
        }


def effective_stale_minutes(settings: Settings) -> int:
    floor = max(15, (settings.worker_timeout_seconds + 119) // 60)
    return max(int(settings.job_stale_minutes), floor)


def cleanup_abandoned_jobs(session: Session, *, stale_minutes: int = 45) -> int:
    stats = _fail_stale_jobs(session, stale_minutes=stale_minutes)
    return stats.abandoned_jobs


def cleanup_expired_files(document_service: DocumentService) -> int:
    return document_service.purge_expired()


def run_runtime_cleanup(session: Session, storage: ObjectStorage, settings: Settings) -> CleanupStats:
    started = time.monotonic()
    stats = CleanupStats()
    token = uuid.uuid4().hex
    if not _acquire_cleanup_lease(session, token):
        stats.skipped = True
        stats.duration_ms = int((time.monotonic() - started) * 1000)
        logger.info("cleanup_skipped reason=lease_held duration_ms=%s", stats.duration_ms)
        return stats
    try:
        stale_minutes = effective_stale_minutes(settings)
        abandoned = _fail_stale_jobs(session, stale_minutes=stale_minutes)
        stats.abandoned_jobs = abandoned.abandoned_jobs
        stats.refunded_credits = abandoned.refunded_credits
        documents = DocumentService(session, storage, settings)
        stats.expired_documents = documents.purge_expired()
        deletion = documents.retry_storage_deletions()
        stats.storage_deleted += deletion["deleted"]
        stats.storage_failures += deletion["failures"]
        stats.storage_retries += deletion["retries"]
    finally:
        _release_cleanup_lease(session, token)
    stats.duration_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        "cleanup_finished abandoned_jobs=%s refunded_credits=%s expired_documents=%s "
        "storage_deleted=%s storage_failures=%s storage_retries=%s duration_ms=%s",
        stats.abandoned_jobs,
        stats.refunded_credits,
        stats.expired_documents,
        stats.storage_deleted,
        stats.storage_failures,
        stats.storage_retries,
        stats.duration_ms,
    )
    return stats


def _fail_stale_jobs(session: Session, *, stale_minutes: int) -> CleanupStats:
    cutoff = datetime.now(UTC) - timedelta(minutes=stale_minutes)
    candidates = list(
        session.scalars(
            select(Job).where(
                Job.status == "processing",
                or_(
                    Job.heartbeat_at < cutoff,
                    and_(Job.heartbeat_at.is_(None), Job.started_at.is_not(None), Job.started_at < cutoff),
                ),
            )
        )
    )
    credits = CreditService(session)
    stats = CleanupStats()
    for job in candidates:
        now = datetime.now(UTC)
        claimed = session.execute(
            update(Job)
            .where(Job.id == job.id, Job.status == "processing")
            .values(
                status="failed",
                error_code="timeout",
                error_message="The worker did not finish before the timeout.",
                completed_at=now,
            )
        )
        session.commit()
        if int(getattr(claimed, "rowcount", 0) or 0) != 1:
            continue
        stats.abandoned_jobs += 1
        user = session.get(User, job.user_id)
        if user and job.credits_reserved:
            credits.refund_reservation(user, job.credits_reserved, job_id=job.id)
            session.commit()
            stats.refunded_credits += job.credits_reserved
        logger.info("abandoned_job_failed refunded_credits=%s", job.credits_reserved if user else 0)
    return stats


def _acquire_cleanup_lease(session: Session, token: str) -> bool:
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        got = session.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": CLEANUP_LOCK_KEY}).scalar()
        session.commit()
        return bool(got)
    now = datetime.now(UTC)
    until = now + timedelta(minutes=LEASE_MINUTES)
    lease = session.get(CleanupLease, LEASE_NAME)
    if lease is None:
        session.add(CleanupLease(name=LEASE_NAME, locked_until=until, token=token))
        session.commit()
        return True
    claimed = session.execute(
        update(CleanupLease)
        .where(
            CleanupLease.name == LEASE_NAME,
            or_(CleanupLease.locked_until.is_(None), CleanupLease.locked_until < now),
        )
        .values(locked_until=until, token=token)
    )
    session.commit()
    return int(getattr(claimed, "rowcount", 0) or 0) == 1


def _release_cleanup_lease(session: Session, token: str) -> None:
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": CLEANUP_LOCK_KEY})
        session.commit()
        return
    session.execute(
        update(CleanupLease)
        .where(CleanupLease.name == LEASE_NAME, CleanupLease.token == token)
        .values(locked_until=None, token=None)
    )
    session.commit()
