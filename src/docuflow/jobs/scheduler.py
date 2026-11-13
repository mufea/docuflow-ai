from __future__ import annotations

import logging
import threading

from sqlalchemy.orm import Session, sessionmaker

from docuflow.cleanup import validate_cleanup_configuration
from docuflow.config import Settings
from docuflow.jobs.retention import run_runtime_cleanup
from docuflow.storage.base import ObjectStorage

logger = logging.getLogger("docuflow.cleanup")


class CleanupScheduler:
    """Interval runner. Does not execute on HTTP requests."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        storage: ObjectStorage,
        settings: Settings,
    ) -> None:
        self.session_factory = session_factory
        self.storage = storage
        self.settings = settings
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        interval = int(self.settings.cleanup_interval_seconds)
        if interval <= 0:
            logger.info("cleanup_scheduler_disabled")
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="docuflow-cleanup",
            daemon=True,
            args=(interval,),
        )
        self._thread.start()
        logger.info("cleanup_scheduler_started interval_seconds=%s", interval)

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=5)
        self._thread = None

    def run_once(self) -> None:
        errors = validate_cleanup_configuration(self.settings)
        if errors:
            for item in errors:
                logger.error("cleanup_config %s", item)
            logger.error("cleanup_scheduler_refused")
            return
        session = self.session_factory()
        try:
            run_runtime_cleanup(session, self.storage, self.settings)
        finally:
            session.close()

    def _loop(self, interval: int) -> None:
        while not self._stop.wait(interval):
            try:
                self.run_once()
            except Exception:
                logger.exception("cleanup_loop_failed")
