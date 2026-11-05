from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import update
from sqlalchemy.orm import Session

from docuflow.billing.ledger import CreditService, RefundResult
from docuflow.jobs.clock import utc_now
from docuflow.models import Job, User

logger = logging.getLogger("docuflow.jobs")


@dataclass(frozen=True, slots=True)
class JobFailResult:
    claimed: bool
    refund: RefundResult | None
    previous_status: str | None


def fail_job_and_refund(
    session: Session,
    job_id: str,
    *,
    code: str,
    message: str,
    expected_statuses: tuple[str, ...] = ("processing",),
    commit: bool = True,
) -> JobFailResult:
    """Mark a job failed and refund its reservation in one transaction.

    The job-row claim is an atomic ``UPDATE ... WHERE status IN expected``.
    The credit refund uses the ledger idempotency key ``refund:{job_id}``.
    Either both persist or, if ``commit`` is true and the transaction is
    rolled back by the caller, neither does.
    """
    job = session.get(Job, job_id)
    if job is None:
        if commit:
            session.rollback()
        return JobFailResult(claimed=False, refund=None, previous_status=None)
    previous = job.status
    claimed = session.execute(
        update(Job)
        .where(Job.id == job_id, Job.status.in_(expected_statuses))
        .values(
            status="failed",
            error_code=code,
            error_message=message,
            completed_at=utc_now(),
        )
    )
    if int(getattr(claimed, "rowcount", 0) or 0) != 1:
        if commit:
            session.rollback()
        return JobFailResult(claimed=False, refund=None, previous_status=previous)
    session.refresh(job)
    refund: RefundResult | None = None
    user = session.get(User, job.user_id)
    if user is not None and job.credits_reserved:
        refund = CreditService(session).refund_reservation(user, job.credits_reserved, job_id=job.id)
    if commit:
        session.commit()
    logger.info(
        "job_failed_refunded id=%s claimed=1 released=%s already_refunded=%s",
        job_id,
        0 if refund is None else refund.released,
        False if refund is None else refund.already_refunded,
    )
    return JobFailResult(claimed=True, refund=refund, previous_status=previous)


def refund_terminal_job(session: Session, job: Job, *, commit: bool = False) -> RefundResult:
    """Refund a failed/cancelled job whose reservation may have been left behind."""
    if job.status not in {"failed", "cancelled"}:
        return RefundResult(skipped=True)
    if job.credits_settled or job.credits_reserved <= 0:
        return RefundResult(skipped=True)
    user = session.get(User, job.user_id)
    if user is None:
        return RefundResult(skipped=True, missing_reservation=True)
    result = CreditService(session).refund_reservation(user, job.credits_reserved, job_id=job.id)
    if commit:
        session.commit()
    return result
