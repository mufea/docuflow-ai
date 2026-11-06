#!/usr/bin/env python3
"""Inspect or apply Alembic 0003 against an isolated staging database.

Requires STAGING_MIGRATE_VERIFY=1. Exits 2 with NOT EXECUTED when unset.
Requires STAGING_DATABASE_CONFIRM to match the database name or host/name
before connecting. Applies upgrades only when STAGING_MIGRATE=1.

Never prints passwords. Never downgrades. Never targets production.
"""

from __future__ import annotations

import os
import sys

from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from docuflow.dsn import normalize_database_url
from docuflow.migrate import upgrade_head
from docuflow.staging_checks import (
    EXPECTED_ALEMBIC_HEAD,
    confirm_matches,
    database_identity,
    emit,
    expected_schema_gaps,
    identity_label,
    is_production_database,
)


def _current_revision(engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _schema_maps(engine) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    inspector = inspect(engine)
    tables = {
        table: {column["name"] for column in inspector.get_columns(table)} for table in inspector.get_table_names()
    }
    indexes = {
        table: {index["name"] for index in inspector.get_indexes(table) if index.get("name")}
        for table in inspector.get_table_names()
    }
    return tables, indexes


def main() -> int:
    if os.environ.get("STAGING_MIGRATE_VERIFY", "").strip() != "1":
        emit("NOT EXECUTED", "staging_migrate_verify", "STAGING_MIGRATE_VERIFY is not 1. No database was contacted.")
        return 2

    raw = os.environ.get("DATABASE_URL", "").strip()
    if not raw:
        emit("FAIL", "database_url", "DATABASE_URL is not set.")
        return 1
    url = normalize_database_url(raw)
    host, name = database_identity(url)
    emit("PASS", "database_identity", identity_label(host, name))
    if url.startswith("sqlite"):
        emit("FAIL", "database_engine", "PostgreSQL is required. Refusing SQLite.")
        return 1
    if is_production_database(
        host,
        name,
        production_host=os.environ.get("PRODUCTION_DATABASE_HOST", ""),
        production_name=os.environ.get("PRODUCTION_DATABASE_NAME", ""),
    ):
        emit("FAIL", "database_isolation", "Identity looks like production. Refusing to continue.")
        return 1
    confirm = os.environ.get("STAGING_DATABASE_CONFIRM", "").strip()
    if not confirm:
        emit("FAIL", "database_confirm", "STAGING_DATABASE_CONFIRM is required (database name or host/database).")
        return 1
    if not confirm_matches(host, name, confirm):
        emit("FAIL", "database_confirm", "STAGING_DATABASE_CONFIRM does not match the parsed identity.")
        return 1
    emit("PASS", "database_confirm", "identity matched STAGING_DATABASE_CONFIRM")

    apply = os.environ.get("STAGING_MIGRATE", "").strip() == "1"
    engine = create_engine(url, pool_pre_ping=True, pool_size=1, max_overflow=0)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        emit("PASS", "database_connectivity", "SELECT 1 succeeded")
        current = _current_revision(engine)
        emit("PASS", "alembic_current", current or "<none>")
        if current != EXPECTED_ALEMBIC_HEAD:
            if not apply:
                emit(
                    "FAIL",
                    "alembic_pending",
                    f"current is {current or '<none>'}; expected {EXPECTED_ALEMBIC_HEAD}. "
                    "Set STAGING_MIGRATE=1 to apply.",
                )
                return 1
            upgrade_head(url)
            current = _current_revision(engine)
            emit("PASS", "alembic_upgrade", current or "<none>")
        else:
            emit("PASS", "alembic_head", "already at expected revision; no migration applied")
        if current != EXPECTED_ALEMBIC_HEAD:
            emit("FAIL", "alembic_head", f"revision is {current or '<none>'}")
            return 1
        gaps = expected_schema_gaps(*_schema_maps(engine))
        if gaps:
            for gap in gaps:
                emit("FAIL", "schema", gap)
            return 1
        emit("PASS", "schema", "required tables, lease columns, and index are present")
    except Exception:
        emit("FAIL", "database_connectivity", "connection or inspection failed")
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
