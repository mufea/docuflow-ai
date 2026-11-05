from __future__ import annotations

import logging
import sys

from docuflow.config import get_settings
from docuflow.db import create_engine_from_settings, session_factory
from docuflow.jobs.retention import run_runtime_cleanup
from docuflow.logging import configure_logging
from docuflow.storage.factory import build_storage

logger = logging.getLogger("docuflow.cleanup")


def main() -> None:
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine_from_settings(settings)
    session = session_factory(engine)()
    try:
        stats = run_runtime_cleanup(session, build_storage(settings), settings)
        if stats.skipped:
            logger.info("cleanup_cli_skipped")
            return
        logger.info("cleanup_cli_ok duration_ms=%s", stats.duration_ms)
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()
    sys.exit(0)
