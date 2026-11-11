from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import and_, or_, update
from sqlalchemy.orm import Session, sessionmaker

from docuflow.jobs.clock import utc_now
from docuflow.models import Job

logger = logging.getLogger("docuflow.jobs")


def stale_processing_clause(cutoff: datetime):
    """SQL predicate: processing liveness is older than ``cutoff``."""
    return or_(
        Job.heartbeat_at < cutoff,
        and_(Job.heartbeat_at.is_(None), Job.started_at.is_not(None), Job.started_at < cutoff),
    )


def touch_processing_heartbeat(
    session_factory: sessionmaker[Session],
    job_id: str,
    *,
    now: Callable[[], datetime] = utc_now,
) -> bool:
    """Persist liveness for a job that is still ``processing``.

    Uses a dedicated session so a worker timer cannot commit uncommitted
    result-document rows on the main job session. Returns True only when
    the database updated one processing row. Database errors propagate.
    """
    session = session_factory()
    try:
        result = session.execute(
            update(Job).where(Job.id == job_id, Job.status == "processing").values(heartbeat_at=now())
        )
        session.commit()
        updated = int(getattr(result, "rowcount", 0) or 0) == 1
        if not updated:
            logger.info("job_heartbeat_skipped id=%s", job_id)
        return updated
    except Exception:
        session.rollback()
        logger.exception("job_heartbeat_failed id=%s", job_id)
        raise
    finally:
        session.close()


class ProcessingHeartbeat:
    """Background liveness pings with a private SQLAlchemy session per tick."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        job_id: str,
        *,
        interval_seconds: float,
    ) -> None:
        self.session_factory = session_factory
        self.job_id = job_id
        self.interval_seconds = float(interval_seconds)
        self.owned = True
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> ProcessingHeartbeat:
        if self.interval_seconds > 0:
            self._thread = threading.Thread(
                target=self._run,
                name=f"job-heartbeat-{self.job_id[:8]}",
                daemon=True,
            )
            self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(2.0, min(self.interval_seconds, 5.0) + 1.0))

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            try:
                if not touch_processing_heartbeat(self.session_factory, self.job_id):
                    self.owned = False
                    return
            except Exception:
                self.owned = False
                return
