from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from docuflow.db import Base
from docuflow.jobs.clock import as_utc, utc_now
from docuflow.jobs.leases import LEASE_NAME, acquire_lease, lease_owner, release_lease, renew_lease
from docuflow.models import CleanupLease


def _factory(tmp_path: Path):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'leases.db'}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_only_one_process_acquires_an_active_lease(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    first = factory()
    second = factory()
    try:
        assert acquire_lease(first, "owner-a", ttl=timedelta(minutes=5)) is True
        assert acquire_lease(second, "owner-b", ttl=timedelta(minutes=5)) is False
        assert lease_owner(first) == "owner-a"
    finally:
        first.close()
        second.close()


def test_expired_lease_can_be_reclaimed(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    first = factory()
    second = factory()
    try:
        assert acquire_lease(first, "owner-a") is True
        row = first.get(CleanupLease, LEASE_NAME)
        assert row is not None
        row.lease_until = utc_now() - timedelta(seconds=5)
        first.commit()
        assert acquire_lease(second, "owner-b") is True
        assert lease_owner(second) == "owner-b"
    finally:
        first.close()
        second.close()


def test_previous_owner_cannot_release_another_owners_lease(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    first = factory()
    second = factory()
    try:
        assert acquire_lease(first, "owner-a") is True
        row = first.get(CleanupLease, LEASE_NAME)
        assert row is not None
        row.lease_until = utc_now() - timedelta(seconds=5)
        first.commit()
        assert acquire_lease(second, "owner-b") is True
        assert release_lease(first, "owner-a") is False
        assert lease_owner(second) == "owner-b"
        assert release_lease(second, "owner-b") is True
        assert lease_owner(second) is None
    finally:
        first.close()
        second.close()


def test_same_owner_can_renew_an_active_lease(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    try:
        assert acquire_lease(session, "owner-a", ttl=timedelta(minutes=1)) is True
        before = session.get(CleanupLease, LEASE_NAME)
        assert before is not None
        original_until = before.lease_until
        assert renew_lease(session, "owner-a", ttl=timedelta(minutes=10)) is True
        after = session.get(CleanupLease, LEASE_NAME)
        assert after is not None and after.lease_until is not None
        assert original_until is not None
        assert as_utc(after.lease_until) > as_utc(original_until)
        assert renew_lease(session, "owner-b") is False
    finally:
        session.close()


def test_cleanup_recovers_after_process_crash(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    crashed = factory()
    recovered = factory()
    try:
        assert acquire_lease(crashed, "crashed-owner") is True
        crashed.close()
        row_session = factory()
        row = row_session.get(CleanupLease, LEASE_NAME)
        assert row is not None
        assert row.owner_token == "crashed-owner"
        row.lease_until = utc_now() - timedelta(minutes=1)
        row_session.commit()
        row_session.close()
        assert acquire_lease(recovered, "new-owner") is True
        assert lease_owner(recovered) == "new-owner"
    finally:
        recovered.close()
