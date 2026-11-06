#!/usr/bin/env python3
"""Validate staging configuration without contacting Render.

Requires STAGING_PREFLIGHT=1. Exits 2 with NOT EXECUTED when unset.
Never prints secrets, passwords, DSNs, or access keys.
Does not create cloud resources.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from docuflow.config import Settings
from docuflow.jobs.recovery import QUEUED_RECOVERY_LIMIT
from docuflow.staging_checks import (
    QUEUED_RECOVERY_LIMIT_REQUIRED,
    audit_staging_blueprint,
    database_identity,
    emit,
    exit_code,
    identity_label,
    validate_staging_configuration,
)


def main() -> int:
    if os.environ.get("STAGING_PREFLIGHT", "").strip() != "1":
        emit("NOT EXECUTED", "staging_preflight", "STAGING_PREFLIGHT is not 1. No configuration was evaluated.")
        return 2

    statuses: list[str] = []
    blueprint = Path("infra/render.staging.yaml")
    if not blueprint.is_file():
        emit("FAIL", "staging_blueprint", "infra/render.staging.yaml is missing.")
        return 1
    blueprint_issues = audit_staging_blueprint(blueprint.read_text())
    if blueprint_issues.errors:
        for item in blueprint_issues.errors:
            emit("FAIL", "staging_blueprint", item)
            statuses.append("FAIL")
    else:
        emit("PASS", "staging_blueprint", "isolated names, inline broker, no Redis, no worker")
        statuses.append("PASS")

    try:
        settings = Settings()
    except Exception:
        emit("FAIL", "staging_config", "settings could not be loaded")
        return 1
    issues = validate_staging_configuration(
        settings,
        production_s3_bucket=os.environ.get("PRODUCTION_S3_BUCKET", ""),
        production_database_host=os.environ.get("PRODUCTION_DATABASE_HOST", ""),
        production_database_name=os.environ.get("PRODUCTION_DATABASE_NAME", ""),
        production_secret=os.environ.get("PRODUCTION_SECRET_KEY", ""),
        production_s3_access_key_id=os.environ.get("PRODUCTION_S3_ACCESS_KEY_ID", ""),
    )
    host, name = database_identity(settings.database_url)
    db_status = "FAIL" if settings.database_url.startswith("sqlite") else "PASS"
    emit(db_status, "database_identity", identity_label(host, name))
    statuses.append(db_status)

    if issues.errors:
        for item in issues.errors:
            emit("FAIL", "staging_config", item)
            statuses.append("FAIL")
    else:
        emit("PASS", "staging_config", "fail-fast, inline broker, dedicated PostgreSQL/S3 checks")
        statuses.append("PASS")
    for item in issues.warnings:
        emit("SKIPPED", "staging_config_warning", item)

    if QUEUED_RECOVERY_LIMIT == QUEUED_RECOVERY_LIMIT_REQUIRED:
        emit("PASS", "queued_job_recovery", f"limit remains {QUEUED_RECOVERY_LIMIT}")
        statuses.append("PASS")
    else:
        emit("FAIL", "queued_job_recovery", f"limit is {QUEUED_RECOVERY_LIMIT}")
        statuses.append("FAIL")
    return exit_code(statuses)  # type: ignore[arg-type]


if __name__ == "__main__":
    sys.exit(main())
