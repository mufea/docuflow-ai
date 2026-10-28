from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Protocol

from docuflow.config import Settings

if TYPE_CHECKING:
    from docuflow.jobs.runner import JobRunner

logger = logging.getLogger("docuflow.broker")


class JobBroker(Protocol):
    def enqueue(self, job_id: str) -> None: ...


class InlineBroker:
    """Runs jobs in a thread pool. Job state is still stored in the database."""

    def __init__(self, runner: JobRunner, *, workers: int = 2) -> None:
        self.runner = runner
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="docuflow-job")

    def enqueue(self, job_id: str) -> None:
        self.pool.submit(self._safe, job_id)

    def _safe(self, job_id: str) -> None:
        try:
            self.runner.process(job_id)
        except Exception:
            logger.exception("inline_job_crash id=%s", job_id)


class RQBroker:
    def __init__(self, redis_url: str, queue_name: str) -> None:
        from redis import Redis
        from rq import Queue

        self.queue = Queue(queue_name, connection=Redis.from_url(redis_url))

    def enqueue(self, job_id: str) -> None:
        self.queue.enqueue("docuflow.worker.process_job", job_id, job_id=f"docuflow-{job_id}")


def build_broker(settings: Settings, runner: JobRunner) -> JobBroker:
    if settings.job_broker == "rq":
        return RQBroker(settings.redis_url, settings.rq_queue_name)
    return InlineBroker(runner, workers=settings.worker_concurrency)
