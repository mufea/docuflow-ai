from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
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
        self._inflight: set[str] = set()
        self._lock = Lock()

    def enqueue(self, job_id: str) -> None:
        with self._lock:
            if job_id in self._inflight:
                return
            self._inflight.add(job_id)
        self.pool.submit(self._safe, job_id)

    def _safe(self, job_id: str) -> None:
        try:
            self.runner.process(job_id)
        except Exception:
            logger.exception("inline_job_crash id=%s", job_id)
        finally:
            with self._lock:
                self._inflight.discard(job_id)


class RQBroker:
    def __init__(self, redis_url: str, queue_name: str, runner: JobRunner, *, workers: int = 2) -> None:
        from redis import Redis
        from rq import Queue

        self.queue = Queue(queue_name, connection=Redis.from_url(redis_url))
        self.inline = InlineBroker(runner, workers=workers)

    def enqueue(self, job_id: str) -> None:
        if self.active_worker_count() > 0:
            try:
                self.queue.enqueue("docuflow.worker.process_job", job_id, job_id=f"docuflow-{job_id}")
                return
            except Exception as exc:
                if type(exc).__name__ == "DuplicateJobError":
                    return
                logger.exception("rq_enqueue_failed id=%s", job_id)
        else:
            logger.warning("rq_no_workers_inline_fallback id=%s", job_id)
        self.inline.enqueue(job_id)

    def active_worker_count(self) -> int:
        try:
            from rq import Worker

            workers = Worker.all(connection=self.queue.connection)
            queue_name = self.queue.name
            count = 0
            for worker in workers:
                names = _worker_queue_names(worker)
                if queue_name in names:
                    count += 1
            return count
        except Exception:
            logger.warning("rq_worker_probe_failed", exc_info=True)
            return 0


def _worker_queue_names(worker: object) -> list[str]:
    names_fn = getattr(worker, "queue_names", None)
    if callable(names_fn):
        return list(names_fn())
    queues = getattr(worker, "queues", [])
    return [getattr(queue, "name", str(queue)) for queue in queues]


def build_broker(settings: Settings, runner: JobRunner) -> JobBroker:
    if settings.job_broker == "rq":
        return RQBroker(
            settings.redis_url,
            settings.rq_queue_name,
            runner,
            workers=settings.worker_concurrency,
        )
    return InlineBroker(runner, workers=settings.worker_concurrency)
