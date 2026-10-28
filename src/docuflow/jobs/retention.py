from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from docuflow.models import Job
from docuflow.services.documents import DocumentService


def cleanup_abandoned_jobs(session: Session, *, stale_minutes: int = 45) -> int:
    cutoff = datetime.now(UTC) - timedelta(minutes=stale_minutes)
    rows = list(session.scalars(select(Job).where(Job.status == "processing", Job.started_at < cutoff)))
    for job in rows:
        job.status = "failed"
        job.error_code = "timeout"
        job.error_message = "The worker did not finish before the timeout."
        job.completed_at = datetime.now(UTC)
    session.commit()
    return len(rows)


def cleanup_expired_files(document_service: DocumentService) -> int:
    return document_service.purge_expired()
