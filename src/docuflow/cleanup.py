from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Callable, Sequence

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from docuflow.config import Settings, get_settings
from docuflow.db import create_engine_from_settings, session_factory
from docuflow.jobs.retention import CleanupStats, run_runtime_cleanup
from docuflow.logging import configure_logging
from docuflow.staging_checks import (
    _has_isolation_token,
    database_identity,
    hostname_from_url,
    is_production_bucket,
)
from docuflow.storage.base import ObjectStorage
from docuflow.storage.factory import build_storage

logger = logging.getLogger("docuflow.cleanup")


class CleanupConfigError(RuntimeError):
    """Raised when cleanup configuration is unsafe to run."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__("Cleanup configuration is unsafe.")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="docuflow-cleanup")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration and exit without connecting or mutating.",
    )
    return parser.parse_args(None if argv is None else list(argv))


def cleanup_context_is_isolated(settings: Settings) -> bool:
    """True when this process appears to be Staging/test, not Production."""
    if _has_isolation_token(os.environ.get("RENDER_SERVICE_NAME", "")):
        return True
    if _has_isolation_token(hostname_from_url(settings.public_api_url)):
        return True
    if _has_isolation_token(hostname_from_url(settings.public_web_url)):
        return True
    host, name = database_identity(settings.database_url)
    return _has_isolation_token(host) or _has_isolation_token(name)


def validate_cleanup_configuration(settings: Settings) -> list[str]:
    """Return unsafe-configuration errors. Empty list means cleanup may run."""
    errors: list[str] = []
    if settings.is_production:
        errors.extend(settings.production_readiness_errors())
    if settings.storage_backend == "s3":
        bucket = settings.s3_bucket.strip()
        if not bucket:
            errors.append("S3_BUCKET is required when STORAGE_BACKEND=s3.")
        elif is_production_bucket(bucket) and cleanup_context_is_isolated(settings):
            errors.append("S3_BUCKET matches a production bucket. Staging cleanup refuses Production buckets.")
        if not settings.reveal_secret(settings.s3_access_key_id) or not settings.reveal_secret(
            settings.s3_secret_access_key
        ):
            errors.append("S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY are required when STORAGE_BACKEND=s3.")
    seen: set[str] = set()
    unique: list[str] = []
    for item in errors:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def run_cleanup_cli(
    settings: Settings,
    *,
    dry_run: bool = False,
    run_cleanup: Callable[[Session, ObjectStorage, Settings], CleanupStats] = run_runtime_cleanup,
    storage_factory: Callable[[Settings], ObjectStorage] = build_storage,
    engine_factory: Callable[[Settings], Engine] = create_engine_from_settings,
    open_session: Callable[[Engine], Session] | None = None,
) -> int:
    errors = validate_cleanup_configuration(settings)
    if errors:
        for item in errors:
            logger.error("cleanup_config %s", item)
        raise CleanupConfigError(errors)
    bucket = settings.s3_bucket.strip() or "<none>"
    if dry_run:
        logger.info("cleanup_cli_dry_run backend=%s bucket=%s", settings.storage_backend, bucket)
        return 0
    make_session = open_session or (lambda engine: session_factory(engine)())
    engine = engine_factory(settings)
    session = make_session(engine)
    try:
        stats = run_cleanup(session, storage_factory(settings), settings)
        if stats.skipped:
            logger.info("cleanup_cli_skipped")
            return 0
        logger.info("cleanup_cli_ok duration_ms=%s", stats.duration_ms)
        return 0
    finally:
        session.close()
        engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    settings = get_settings()
    configure_logging(settings)
    try:
        return run_cleanup_cli(settings, dry_run=args.dry_run)
    except CleanupConfigError:
        return 1


if __name__ == "__main__":
    sys.exit(main())
