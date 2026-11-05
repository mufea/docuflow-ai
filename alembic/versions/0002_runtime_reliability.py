"""runtime cleanup lease, storage deletion outbox, job heartbeat

Revision ID: 0002_runtime_reliability
Revises: 0001_initial
Create Date: 2026-11-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_runtime_reliability"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "storage_deletions",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("document_id", sa.String(length=32), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_error", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("storage_key", name="uq_storage_deletion_key"),
    )
    op.create_index("ix_storage_deletions_document_id", "storage_deletions", ["document_id"])
    op.create_index("ix_storage_deletions_status", "storage_deletions", ["status"])
    op.create_table(
        "cleanup_leases",
        sa.Column("name", sa.String(length=32), primary_key=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token", sa.String(length=64), nullable=True),
    )
    op.execute("INSERT INTO cleanup_leases (name) VALUES ('runtime')")


def downgrade() -> None:
    op.drop_table("cleanup_leases")
    op.drop_index("ix_storage_deletions_status", table_name="storage_deletions")
    op.drop_index("ix_storage_deletions_document_id", table_name="storage_deletions")
    op.drop_table("storage_deletions")
    op.drop_column("jobs", "heartbeat_at")
