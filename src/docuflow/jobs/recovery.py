from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from docuflow.models import Job

if TYPE_CHECKING:
    from docuflow.jobs.broker import JobBroker

logger = logging.getLogger("docuflow.jobs")

QUEUED_RECOVERY_LIMIT = 100


def recover_queued_jobs(
    session_factory: sessionmaker[Session],
    broker: JobBroker,
    *,
    limit: int = QUEUED_RECOVERY_LIMIT,
) -> int:
    """Re-enqueue durable ``queued`` rows after an API or worker restart.

    Postgres remains the source of truth. Duplicate delivery is safe because
    the runner claims a row only when ``status=queued``. Processing rows are
    left for stale-job cleanup so a live worker is not interrupted.
    """
    cap = max(0, int(limit))
    if cap == 0:
        return 0
    session = session_factory()
    try:
        job_ids = list(
            session.scalars(select(Job.id).where(Job.status == "queued").order_by(Job.created_at.asc()).limit(cap))
        )
    finally:
        session.close()
    for job_id in job_ids:
        broker.enqueue(job_id)
    if job_ids:
        logger.info("queued_jobs_recovered count=%s", len(job_ids))
    return len(job_ids)
