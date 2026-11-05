from __future__ import annotations

import uuid
from collections.abc import Generator
from contextlib import contextmanager

import pytest
from alembic import command
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from docuflow.dsn import normalize_database_url
from docuflow.jobs.leases import acquire_lease, release_lease
from docuflow.migrate import alembic_config
from docuflow.models import CleanupLease

pytestmark = pytest.mark.integration

HEAD_REVISION = "0003_cost_efficient_reliability"
PREVIOUS_REVISION = "0002_runtime_reliability"
SEEDED_DELETION_ID = "a" * 32
SEEDED_STORAGE_KEY = "phase95/keep-me.bin"
SEEDED_ATTEMPTS = 3


@contextmanager
def isolated_empty_database(pg_admin_url: str) -> Generator[tuple[Engine, object, str], None, None]:
    admin = create_engine(pg_admin_url, isolation_level="AUTOCOMMIT", future=True)
    db_name = f"df_mig_{uuid.uuid4().hex[:12]}"
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin.dispose()
    url = normalize_database_url(pg_admin_url.rsplit("/", 1)[0] + f"/{db_name}")
    engine = create_engine(url, future=True)
    config = alembic_config()
    config.set_main_option("sqlalchemy.url", url)
    try:
        yield engine, config, url
    finally:
        engine.dispose()
        cleanup = create_engine(pg_admin_url, isolation_level="AUTOCOMMIT", future=True)
        with cleanup.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
        cleanup.dispose()


def _current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def test_alembic_upgrade_head_adds_phase92_columns(pg_admin_url: str) -> None:
    with isolated_empty_database(pg_admin_url) as (engine, config, _url):
        command.upgrade(config, "head")
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert "cleanup_leases" in tables
        assert "storage_deletions" in tables
        lease_cols = {column["name"] for column in inspector.get_columns("cleanup_leases")}
        assert {"name", "token", "locked_until", "acquired_at", "updated_at"} <= lease_cols
        deletion_cols = {column["name"]: column["nullable"] for column in inspector.get_columns("storage_deletions")}
        assert {"started_at", "lease_until", "owner_token", "attempts", "last_error"} <= set(deletion_cols)
        assert deletion_cols["started_at"] is True
        assert deletion_cols["lease_until"] is True
        assert deletion_cols["owner_token"] is True
        index_names = {index["name"] for index in inspector.get_indexes("storage_deletions")}
        assert "ix_storage_deletions_lease_until" in index_names
        script = ScriptDirectory.from_config(config)
        assert script.get_heads() == [HEAD_REVISION]
        assert _current_revision(engine) == HEAD_REVISION


def test_alembic_0003_preserves_rows_then_downgrades_disposable_db(pg_admin_url: str) -> None:
    with isolated_empty_database(pg_admin_url) as (engine, config, _url):
        command.upgrade(config, PREVIOUS_REVISION)
        assert _current_revision(engine) == PREVIOUS_REVISION
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO storage_deletions (id, storage_key, status, attempts, max_attempts) "
                    "VALUES (:id, :key, 'pending', :attempts, 8)"
                ),
                {"id": SEEDED_DELETION_ID, "key": SEEDED_STORAGE_KEY, "attempts": SEEDED_ATTEMPTS},
            )
            connection.execute(
                text("UPDATE cleanup_leases SET token = :token WHERE name = 'runtime'"),
                {"token": "seed-owner-token"},
            )

        command.upgrade(config, HEAD_REVISION)
        assert _current_revision(engine) == HEAD_REVISION
        inspector = inspect(engine)
        lease_nulls = {column["name"]: column["nullable"] for column in inspector.get_columns("cleanup_leases")}
        assert lease_nulls["acquired_at"] is True
        assert lease_nulls["updated_at"] is True
        index_names = {index["name"] for index in inspector.get_indexes("storage_deletions")}
        assert "ix_storage_deletions_lease_until" in index_names

        with engine.connect() as connection:
            deletion = connection.execute(
                text(
                    "SELECT storage_key, attempts, status, owner_token, started_at, lease_until "
                    "FROM storage_deletions WHERE id = :id"
                ),
                {"id": SEEDED_DELETION_ID},
            ).one()
            assert deletion.storage_key == SEEDED_STORAGE_KEY
            assert deletion.attempts == SEEDED_ATTEMPTS
            assert deletion.status == "pending"
            assert deletion.owner_token is None
            assert deletion.started_at is None
            assert deletion.lease_until is None
            lease = connection.execute(
                text("SELECT token, acquired_at, updated_at FROM cleanup_leases WHERE name = 'runtime'")
            ).one()
            assert lease.token == "seed-owner-token"
            assert lease.acquired_at is None
            assert lease.updated_at is None

        session = sessionmaker(bind=engine, expire_on_commit=False)()
        try:
            assert acquire_lease(session, "phase95-worker") is True
            row = session.get(CleanupLease, "runtime")
            assert row is not None
            assert row.owner_token == "phase95-worker"
            assert row.acquired_at is not None
            assert row.lease_until is not None
            assert release_lease(session, "phase95-worker") is True
        finally:
            session.close()

        command.downgrade(config, PREVIOUS_REVISION)
        assert _current_revision(engine) == PREVIOUS_REVISION
        inspector = inspect(engine)
        lease_cols = {column["name"] for column in inspector.get_columns("cleanup_leases")}
        assert "acquired_at" not in lease_cols
        assert "updated_at" not in lease_cols
        deletion_cols = {column["name"] for column in inspector.get_columns("storage_deletions")}
        assert "owner_token" not in deletion_cols
        assert "lease_until" not in deletion_cols
        assert "started_at" not in deletion_cols
        index_names = {index["name"] for index in inspector.get_indexes("storage_deletions")}
        assert "ix_storage_deletions_lease_until" not in index_names
        with engine.connect() as connection:
            surviving = connection.execute(
                text("SELECT storage_key, attempts FROM storage_deletions WHERE id = :id"),
                {"id": SEEDED_DELETION_ID},
            ).one()
            assert surviving.storage_key == SEEDED_STORAGE_KEY
            assert surviving.attempts == SEEDED_ATTEMPTS
