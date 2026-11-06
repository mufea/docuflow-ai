from __future__ import annotations

import os
import subprocess
import sys

import pytest
from alembic import command

from docuflow.staging_checks import EXPECTED_ALEMBIC_HEAD, database_identity
from tests.integration.test_migrations import PREVIOUS_REVISION, isolated_empty_database

pytestmark = pytest.mark.integration


def _run(url: str, name: str, extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["STAGING_MIGRATE_VERIFY"] = "1"
    env["DATABASE_URL"] = url
    env["STAGING_DATABASE_CONFIRM"] = name
    env.pop("STAGING_MIGRATE", None)
    if extra:
        env.update(extra)
    return subprocess.run(  # noqa: S603
        [sys.executable, "scripts/staging_migrate_verify.py"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_migrate_verify_pending_without_apply_permission(pg_admin_url: str) -> None:
    with isolated_empty_database(pg_admin_url) as (_engine, config, url):
        command.upgrade(config, PREVIOUS_REVISION)
        _host, name = database_identity(url)
        result = _run(url, name)
        assert result.returncode == 1, result.stdout + result.stderr
        assert "STAGING_MIGRATE=1" in result.stdout
        assert "supersecret" not in result.stdout
        assert "password=" not in result.stdout.lower()


def test_migrate_verify_already_current(pg_admin_url: str) -> None:
    with isolated_empty_database(pg_admin_url) as (_engine, config, url):
        command.upgrade(config, "head")
        _host, name = database_identity(url)
        result = _run(url, name)
        assert result.returncode == 0, result.stdout + result.stderr
        assert EXPECTED_ALEMBIC_HEAD in result.stdout
        assert "already at expected revision" in result.stdout
        assert "password=" not in result.stdout.lower()


def test_migrate_verify_apply_on_disposable_database(pg_admin_url: str) -> None:
    with isolated_empty_database(pg_admin_url) as (engine, config, url):
        command.upgrade(config, PREVIOUS_REVISION)
        _host, name = database_identity(url)
        result = _run(url, name, {"STAGING_MIGRATE": "1"})
        assert result.returncode == 0, result.stdout + result.stderr
        assert "alembic_upgrade" in result.stdout or EXPECTED_ALEMBIC_HEAD in result.stdout
        assert "password=" not in result.stdout.lower()
        with engine.connect() as connection:
            from alembic.runtime.migration import MigrationContext

            current = MigrationContext.configure(connection).get_current_revision()
        assert current == EXPECTED_ALEMBIC_HEAD
