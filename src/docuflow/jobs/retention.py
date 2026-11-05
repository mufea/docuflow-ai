from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from docuflow.config import Settings
from docuflow.jobs.clock import as_utc, utc_now
from docuflow.jobs.leases import LEASE_NAME, LeaseGuard, acquire_lease, release_lease
from docuflow.jobs.refunds import fail_job_and_refund, refund_terminal_job
from docuflow.models import Job
from docuflow.services.documents import DocumentService
from docuflow.storage.base import ObjectStorage

logger = logging.getLogger("docuflow.cleanup")

# Kept for tests and docs that still mention the historical advisory-lock key.
CLEANUP_LOCK_KEY = 86420139
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
    aborted: bool = False

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
            "aborted": self.aborted,
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
    ttl = timedelta(minutes=max(1, int(settings.cleanup_lease_minutes)))
    if not acquire_lease(session, token, name=LEASE_NAME, ttl=ttl):
        stats.skipped = True
        stats.duration_ms = int((time.monotonic() - started) * 1000)
        logger.info("cleanup_skipped reason=lease_held duration_ms=%s", stats.duration_ms)
        return stats
    guard = LeaseGuard(session, token, name=LEASE_NAME, ttl=ttl)
    try:
        stale_minutes = effective_stale_minutes(settings)
        if _hold(guard, stats):
            abandoned = _fail_stale_jobs(session, stale_minutes=stale_minutes, heartbeat=guard.heartbeat)
            stats.abandoned_jobs = abandoned.abandoned_jobs
            stats.refunded_credits = abandoned.refunded_credits
            stats.aborted = stats.aborted or abandoned.aborted
        if _hold(guard, stats):
            recovered = _refund_stranded_terminal_jobs(session, heartbeat=guard.heartbeat)
            stats.refunded_credits += recovered.refunded_credits
            stats.aborted = stats.aborted or recovered.aborted
        documents: DocumentService | None = None
        if _hold(guard, stats):
            documents = DocumentService(session, storage, settings)
            stats.expired_documents = documents.purge_expired(heartbeat=guard.heartbeat)
            if guard.lost:
                stats.aborted = True
        if _hold(guard, stats) and documents is not None:
            deletion = documents.retry_storage_deletions(heartbeat=guard.heartbeat)
            stats.storage_deleted += deletion["deleted"]
            stats.storage_failures += deletion["failures"]
            stats.storage_retries += deletion["retries"]
            if guard.lost:
                stats.aborted = True
        if stats.aborted:
            logger.warning("cleanup_aborted reason=lease_lost duration_ms=%s", int((time.monotonic() - started) * 1000))
    except Exception:
        session.rollback()
        raise
    finally:
        try:
            release_lease(session, token, name=LEASE_NAME)
        except Exception:
            logger.exception("cleanup_lease_release_failed")
            session.rollback()
    stats.duration_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        "cleanup_finished abandoned_jobs=%s refunded_credits=%s expired_documents=%s "
        "storage_deleted=%s storage_failures=%s storage_retries=%s duration_ms=%s aborted=%s",
        stats.abandoned_jobs,
        stats.refunded_credits,
        stats.expired_documents,
        stats.storage_deleted,
        stats.storage_failures,
        stats.storage_retries,
        stats.duration_ms,
        stats.aborted,
    )
    return stats


def _hold(guard: LeaseGuard, stats: CleanupStats) -> bool:
    if stats.aborted:
        return False
    if guard.heartbeat():
        return True
    stats.aborted = True
    return False


def _fail_stale_jobs(
    session: Session,
    *,
    stale_minutes: int,
    heartbeat: Callable[[], bool] | None = None,
) -> CleanupStats:
    cutoff = utc_now() - timedelta(minutes=stale_minutes)
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
    stats = CleanupStats()
    for job in candidates:
        if heartbeat is not None and not heartbeat():
            stats.aborted = True
            break
        last_beat = as_utc(job.heartbeat_at) if job.heartbeat_at is not None else None
        started = as_utc(job.started_at) if job.started_at is not None else None
        if last_beat is not None and last_beat >= cutoff:
            continue
        if last_beat is None and started is not None and started >= cutoff:
            continue
        result = fail_job_and_refund(
            session,
            job.id,
            code="timeout",
            message="The worker did not finish before the timeout.",
            expected_statuses=("processing",),
            commit=True,
        )
        if not result.claimed:
            continue
        stats.abandoned_jobs += 1
        if result.refund is not None:
            stats.refunded_credits += result.refund.released
        logger.info(
            "abandoned_job_failed refunded_credits=%s already_refunded=%s",
            0 if result.refund is None else result.refund.released,
            False if result.refund is None else result.refund.already_refunded,
        )
    return stats


def _refund_stranded_terminal_jobs(
    session: Session,
    *,
    heartbeat: Callable[[], bool] | None = None,
) -> CleanupStats:
    """Recover reservations left behind if a historical fail committed without a refund."""
    stats = CleanupStats()
    rows = list(
        session.scalars(
            select(Job).where(
                Job.status.in_(("failed", "cancelled")),
                Job.credits_reserved > 0,
                Job.credits_settled == 0,
            )
        )
    )
    for job in rows:
        if heartbeat is not None and not heartbeat():
            stats.aborted = True
            break
        result = refund_terminal_job(session, job, commit=True)
        if result.released:
            stats.refunded_credits += result.released
    return stats
