from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from docuflow.jobs.clock import as_utc, utc_now
from docuflow.models import CleanupLease

logger = logging.getLogger("docuflow.cleanup")

LEASE_NAME = "runtime"
LEASE_MINUTES = 5


def acquire_lease(
    session: Session,
    owner_token: str,
    *,
    name: str = LEASE_NAME,
    ttl: timedelta | None = None,
) -> bool:
    """Atomically take exclusive ownership of a named lease.

    Expired leases are reclaimable. An active owner may renew. The row is
    committed so other connections can observe ownership without relying on
    session-level PostgreSQL advisory locks (unsafe with connection pooling).
    """
    now = utc_now()
    until = now + (ttl if ttl is not None else timedelta(minutes=LEASE_MINUTES))
    _ensure_lease_row(session, name)
    claimed = session.execute(
        update(CleanupLease)
        .where(
            CleanupLease.name == name,
            or_(
                CleanupLease.lease_until.is_(None),
                CleanupLease.lease_until < now,
                CleanupLease.owner_token == owner_token,
            ),
        )
        .values(
            owner_token=owner_token,
            acquired_at=now,
            lease_until=until,
            updated_at=now,
        )
    )
    session.commit()
    won = int(getattr(claimed, "rowcount", 0) or 0) == 1
    if won:
        logger.info("cleanup_lease_acquired name=%s", name)
    return won


def renew_lease(
    session: Session,
    owner_token: str,
    *,
    name: str = LEASE_NAME,
    ttl: timedelta | None = None,
) -> bool:
    now = utc_now()
    until = now + (ttl if ttl is not None else timedelta(minutes=LEASE_MINUTES))
    renewed = session.execute(
        update(CleanupLease)
        .where(CleanupLease.name == name, CleanupLease.owner_token == owner_token)
        .values(lease_until=until, updated_at=now)
    )
    session.commit()
    return int(getattr(renewed, "rowcount", 0) or 0) == 1


def release_lease(session: Session, owner_token: str, *, name: str = LEASE_NAME) -> bool:
    """Release only if ``owner_token`` still owns the lease."""
    now = utc_now()
    released = session.execute(
        update(CleanupLease)
        .where(CleanupLease.name == name, CleanupLease.owner_token == owner_token)
        .values(owner_token=None, lease_until=None, updated_at=now)
    )
    session.commit()
    won = int(getattr(released, "rowcount", 0) or 0) == 1
    if won:
        logger.info("cleanup_lease_released name=%s", name)
    return won


def lease_owner(session: Session, *, name: str = LEASE_NAME) -> str | None:
    row = session.get(CleanupLease, name)
    if row is None or row.owner_token is None:
        return None
    if row.lease_until is None:
        return None
    if as_utc(row.lease_until) < utc_now():
        return None
    return row.owner_token


def _ensure_lease_row(session: Session, name: str) -> None:
    if session.get(CleanupLease, name) is not None:
        return
    try:
        with session.begin_nested():
            session.add(CleanupLease(name=name))
            session.flush()
    except IntegrityError:
        existing = session.execute(select(CleanupLease).where(CleanupLease.name == name)).scalar_one_or_none()
        if existing is None:
            raise
