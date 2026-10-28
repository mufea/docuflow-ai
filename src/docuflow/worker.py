from __future__ import annotations

import logging
import signal
import sys

from docuflow.ai.providers import build_ai_provider
from docuflow.config import get_settings
from docuflow.db import create_engine_from_settings, session_factory
from docuflow.jobs.runner import JobRunner
from docuflow.logging import configure_logging
from docuflow.storage.factory import build_storage

logger = logging.getLogger("docuflow.worker")


def process_job(job_id: str) -> None:
    settings = get_settings()
    engine = create_engine_from_settings(settings)
    factory = session_factory(engine)
    runner = JobRunner(
        session_factory=factory,
        storage=build_storage(settings),
        settings=settings,
        ai=build_ai_provider(settings),
    )
    runner.process(job_id)


def run() -> None:
    settings = get_settings()
    configure_logging(settings)
    if settings.job_broker != "rq":
        logger.error("Worker process requires JOB_BROKER=rq")
        sys.exit(1)
    from redis import Redis
    from rq import Worker

    connection = Redis.from_url(settings.redis_url)
    worker = Worker([settings.rq_queue_name], connection=connection)

    def _shutdown(_signum: int, _frame: object) -> None:
        logger.info("worker_shutdown")
        if hasattr(worker, "request_stop"):
            worker.request_stop()  # type: ignore[call-arg]

    signal.signal(signal.SIGTERM, _shutdown)
    logger.info("worker_start queue=%s", settings.rq_queue_name)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    run()
