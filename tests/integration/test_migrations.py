from __future__ import annotations

import uuid

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text

from docuflow.dsn import normalize_database_url
from docuflow.migrate import alembic_config

pytestmark = pytest.mark.integration


def test_alembic_upgrade_head_adds_phase92_columns(pg_admin_url: str) -> None:
    admin = create_engine(pg_admin_url, isolation_level="AUTOCOMMIT", future=True)
    db_name = f"df_mig_{uuid.uuid4().hex[:12]}"
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin.dispose()
    url = normalize_database_url(pg_admin_url.rsplit("/", 1)[0] + f"/{db_name}")
    engine = create_engine(url, future=True)
    try:
        config = alembic_config()
        config.set_main_option("sqlalchemy.url", url)
        command.upgrade(config, "head")
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert "cleanup_leases" in tables
        assert "storage_deletions" in tables
        lease_cols = {column["name"] for column in inspector.get_columns("cleanup_leases")}
        assert {"name", "token", "locked_until", "acquired_at", "updated_at"} <= lease_cols
        deletion_cols = {column["name"] for column in inspector.get_columns("storage_deletions")}
        assert {"started_at", "lease_until", "owner_token", "attempts", "last_error"} <= deletion_cols
    finally:
        engine.dispose()
        cleanup = create_engine(pg_admin_url, isolation_level="AUTOCOMMIT", future=True)
        with cleanup.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
        cleanup.dispose()
