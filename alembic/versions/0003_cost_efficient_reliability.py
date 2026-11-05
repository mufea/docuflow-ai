"""cleanup lease timestamps and recoverable storage deletion leases

Revision ID: 0003_cost_efficient_reliability
Revises: 0002_runtime_reliability
Create Date: 2026-11-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_cost_efficient_reliability"
down_revision: str | None = "0002_runtime_reliability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cleanup_leases", sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("cleanup_leases", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("storage_deletions", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("storage_deletions", sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("storage_deletions", sa.Column("owner_token", sa.String(length=64), nullable=True))
    op.create_index("ix_storage_deletions_lease_until", "storage_deletions", ["lease_until"])


def downgrade() -> None:
    op.drop_index("ix_storage_deletions_lease_until", table_name="storage_deletions")
    op.drop_column("storage_deletions", "owner_token")
    op.drop_column("storage_deletions", "lease_until")
    op.drop_column("storage_deletions", "started_at")
    op.drop_column("cleanup_leases", "updated_at")
    op.drop_column("cleanup_leases", "acquired_at")
