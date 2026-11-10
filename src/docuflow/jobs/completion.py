from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session

from docuflow.jobs.clock import utc_now
from docuflow.models import Job

logger = logging.getLogger("docuflow.jobs")


@dataclass(frozen=True, slots=True)
class JobCompleteResult:
    claimed: bool
    previous_status: str | None


def complete_job_if_processing(
    session: Session,
    job_id: str,
    *,
    result_payload: dict[str, Any] | None = None,
    result_document_ids: list[str] | None = None,
    commit: bool = False,
) -> JobCompleteResult:
    """Mark a job completed only when its current status is processing.

    The status predicate is enforced by the database:

    ``UPDATE jobs SET status='completed' ... WHERE id=:id AND status='processing'``

    A zero-row update is an unsuccessful completion. Callers must inspect
    ``claimed`` and must not settle credits or treat the job as completed.
    """
    job = session.get(Job, job_id)
    if job is None:
        if commit:
            session.rollback()
        logger.info("job_skip_not_processing id=%s previous=missing", job_id)
        return JobCompleteResult(claimed=False, previous_status=None)
    previous = job.status
    values: dict[str, Any] = {
        "status": "completed",
        "progress": 100,
        "completed_at": utc_now(),
    }
    if result_payload is not None:
        values["result_payload"] = result_payload
    if result_document_ids is not None:
        values["result_document_ids"] = result_document_ids
    claimed = session.execute(update(Job).where(Job.id == job_id, Job.status == "processing").values(**values))
    if int(getattr(claimed, "rowcount", 0) or 0) != 1:
        if commit:
            session.rollback()
        logger.info("job_skip_not_processing id=%s previous=%s", job_id, previous)
        return JobCompleteResult(claimed=False, previous_status=previous)
    session.refresh(job)
    if commit:
        session.commit()
    logger.info("job_completed id=%s", job_id)
    return JobCompleteResult(claimed=True, previous_status=previous)
