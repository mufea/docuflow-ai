from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from docuflow.config import Settings
from docuflow.db import Base
from docuflow.jobs.clock import as_utc, utc_now
from docuflow.jobs.leases import LEASE_NAME, LeaseGuard, acquire_lease, lease_owner, release_lease, renew_lease
from docuflow.jobs.retention import run_runtime_cleanup
from docuflow.models import CleanupLease
from docuflow.services.documents import DocumentService
from docuflow.storage.filesystem import FilesystemStorage


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


def test_successful_lease_renewal_after_ttl_elapses(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    try:
        assert acquire_lease(session, "owner-a", ttl=timedelta(seconds=1)) is True
        row = session.get(CleanupLease, LEASE_NAME)
        assert row is not None
        row.lease_until = utc_now() - timedelta(seconds=5)
        session.commit()
        guard = LeaseGuard(session, "owner-a", ttl=timedelta(minutes=5))
        assert guard.heartbeat() is True
        assert lease_owner(session) == "owner-a"
        after = session.get(CleanupLease, LEASE_NAME)
        assert after is not None and after.lease_until is not None
        assert as_utc(after.lease_until) > utc_now()
    finally:
        session.close()


def test_failed_renewal_after_ownership_changes(tmp_path: Path) -> None:
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
        assert renew_lease(first, "owner-a") is False
        assert lease_owner(second) == "owner-b"
        assert release_lease(first, "owner-a") is False
        assert lease_owner(second) == "owner-b"
    finally:
        first.close()
        second.close()


def test_cleanup_renews_lease_when_run_exceeds_ttl(tmp_path: Path, monkeypatch) -> None:
    factory = _factory(tmp_path)
    session = factory()
    settings = Settings(
        env="test",
        secret_key="test-secret-key-please-change",
        cleanup_interval_seconds=0,
        cleanup_lease_minutes=5,
        job_stale_minutes=90,
        storage_local_path=str(tmp_path / "storage"),
    )
    storage = FilesystemStorage(tmp_path / "storage")
    renewals = {"n": 0}
    original_purge = DocumentService.purge_expired

    def expire_then_purge(self: DocumentService, **kwargs) -> int:
        row = self.session.get(CleanupLease, LEASE_NAME)
        assert row is not None
        row.lease_until = utc_now() - timedelta(seconds=30)
        self.session.commit()
        return original_purge(self, **kwargs)

    original_renew = renew_lease

    def counting_renew(session, owner_token, **kwargs):
        renewals["n"] += 1
        return original_renew(session, owner_token, **kwargs)

    monkeypatch.setattr(DocumentService, "purge_expired", expire_then_purge)
    monkeypatch.setattr("docuflow.jobs.leases.renew_lease", counting_renew)
    try:
        stats = run_runtime_cleanup(session, storage, settings)
        assert stats.skipped is False
        assert stats.aborted is False
        assert renewals["n"] >= 1
    finally:
        session.close()


def test_lost_lease_stops_remaining_cleanup_work(tmp_path: Path, monkeypatch) -> None:
    factory = _factory(tmp_path)
    holder = factory()
    session = factory()
    settings = Settings(
        env="test",
        secret_key="test-secret-key-please-change",
        cleanup_interval_seconds=0,
        cleanup_lease_minutes=5,
        job_stale_minutes=90,
        storage_local_path=str(tmp_path / "storage"),
    )
    storage = FilesystemStorage(tmp_path / "storage")
    stages = []

    def steal_then_purge(self: DocumentService, **kwargs) -> int:
        stages.append("purge")
        row = self.session.get(CleanupLease, LEASE_NAME)
        assert row is not None
        row.lease_until = utc_now() - timedelta(seconds=5)
        self.session.commit()
        assert acquire_lease(holder, "replacement-owner", ttl=timedelta(minutes=5)) is True
        return 0

    def fail_if_retry(self: DocumentService, **kwargs):
        stages.append("retry")
        raise AssertionError("retry_storage_deletions must not run after lease loss")

    monkeypatch.setattr(DocumentService, "purge_expired", steal_then_purge)
    monkeypatch.setattr(DocumentService, "retry_storage_deletions", fail_if_retry)
    try:
        stats = run_runtime_cleanup(session, storage, settings)
        assert stats.skipped is False
        assert stats.aborted is True
        assert stages == ["purge"]
        assert lease_owner(holder) == "replacement-owner"
        assert release_lease(session, "should-not-match") is False
        assert lease_owner(holder) == "replacement-owner"
    finally:
        session.close()
        holder.close()


def test_concurrent_cleanup_second_process_skips(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    first = factory()
    second = factory()
    settings = Settings(
        env="test",
        secret_key="test-secret-key-please-change",
        cleanup_interval_seconds=0,
        cleanup_lease_minutes=5,
        job_stale_minutes=90,
        storage_local_path=str(tmp_path / "storage"),
    )
    storage = FilesystemStorage(tmp_path / "storage")
    try:
        stats_first = run_runtime_cleanup(first, storage, settings)
        assert stats_first.skipped is False
        assert acquire_lease(first, "held-during-second", ttl=timedelta(minutes=5)) is True
        stats_second = run_runtime_cleanup(second, storage, settings)
        assert stats_second.skipped is True
        assert stats_second.abandoned_jobs == 0
        assert release_lease(second, "not-the-owner") is False
        assert lease_owner(first) == "held-during-second"
    finally:
        first.close()
        second.close()
