from __future__ import annotations

import threading
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from docuflow.billing.ledger import CreditService
from docuflow.config import Settings
from docuflow.jobs.clock import utc_now
from docuflow.jobs.leases import LEASE_NAME, acquire_lease, release_lease
from docuflow.jobs.refunds import fail_job_and_refund
from docuflow.jobs.retention import run_runtime_cleanup
from docuflow.models import CleanupLease, CreditLedger, Job, StorageDeletion, User
from docuflow.services.documents import DocumentService
from docuflow.storage.filesystem import FilesystemStorage

pytestmark = pytest.mark.integration


def _user(session: Session) -> User:
    return session.query(User).one()


def test_postgres_concurrent_refunds_are_idempotent(
    pg_session: Session, pg_session_factory: sessionmaker[Session]
) -> None:
    user = _user(pg_session)
    credits = CreditService(pg_session)
    credits.ensure_account(user)
    job = Job(user_id=user.id, operation="extract_text", status="processing", credits_reserved=5)
    pg_session.add(job)
    pg_session.commit()
    credits.reserve(user, 5, job_id=job.id)
    pg_session.commit()
    job_id = job.id
    user_id = user.id
    barrier = threading.Barrier(2)
    results: list[int] = []
    errors: list[BaseException] = []

    def worker() -> None:
        session = pg_session_factory()
        try:
            barrier.wait(timeout=5)
            local_user = session.get(User, user_id)
            assert local_user is not None
            result = CreditService(session).refund_reservation(local_user, 5, job_id=job_id)
            session.commit()
            results.append(result.released)
        except Exception as exc:
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert errors == []
    assert sorted(results) == [0, 5] or results.count(5) == 1
    assert sum(results) == 5
    pg_session.expire_all()
    account = CreditService(pg_session).ensure_account(pg_session.get(User, user_id))
    assert account.reserved == 0
    assert account.balance == 20
    refunds = list(pg_session.query(CreditLedger).filter_by(idempotency_key=f"refund:{job_id}"))
    assert len(refunds) == 1


def test_postgres_job_fail_and_refund_atomicity(pg_session: Session) -> None:
    user = _user(pg_session)
    CreditService(pg_session).ensure_account(user)
    job = Job(user_id=user.id, operation="extract_text", status="processing", credits_reserved=4)
    pg_session.add(job)
    pg_session.commit()
    CreditService(pg_session).reserve(user, 4, job_id=job.id)
    pg_session.commit()
    result = fail_job_and_refund(pg_session, job.id, code="timeout", message="atomic", commit=False)
    assert result.claimed is True
    pg_session.rollback()
    pg_session.refresh(job)
    account = CreditService(pg_session).ensure_account(user)
    assert job.status == "processing"
    assert account.reserved == 4
    committed = fail_job_and_refund(pg_session, job.id, code="timeout", message="atomic", commit=True)
    pg_session.refresh(job)
    account = CreditService(pg_session).ensure_account(user)
    assert committed.claimed is True
    assert job.status == "failed"
    assert account.reserved == 0


def test_postgres_lease_acquisition_is_concurrency_safe(pg_session_factory: sessionmaker[Session]) -> None:
    barrier = threading.Barrier(2)
    wins: list[str] = []
    errors: list[BaseException] = []

    def worker(token: str) -> None:
        session = pg_session_factory()
        try:
            barrier.wait(timeout=5)
            if acquire_lease(session, token, ttl=timedelta(minutes=5)):
                wins.append(token)
        except Exception as exc:
            errors.append(exc)
        finally:
            session.close()

    threads = [
        threading.Thread(target=worker, args=("alpha",)),
        threading.Thread(target=worker, args=("beta",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert errors == []
    assert len(wins) == 1
    session = pg_session_factory()
    try:
        row = session.get(CleanupLease, LEASE_NAME)
        assert row is not None
        assert row.owner_token == wins[0]
        assert release_lease(session, "not-owner") is False
        assert release_lease(session, wins[0]) is True
    finally:
        session.close()


def test_postgres_expired_lease_recovery(pg_session: Session, pg_session_factory: sessionmaker[Session]) -> None:
    assert acquire_lease(pg_session, "old-owner") is True
    row = pg_session.get(CleanupLease, LEASE_NAME)
    assert row is not None
    row.lease_until = utc_now() - timedelta(seconds=2)
    pg_session.commit()
    other = pg_session_factory()
    try:
        assert acquire_lease(other, "new-owner") is True
        assert release_lease(pg_session, "old-owner") is False
    finally:
        other.close()


def test_postgres_storage_deletion_concurrent_claims(
    pg_session: Session, pg_session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    settings = Settings(
        env="test",
        secret_key="test-secret-key-please-change",
        storage_delete_max_attempts=8,
        storage_delete_lease_minutes=5,
        cleanup_interval_seconds=0,
    )
    storage = FilesystemStorage(tmp_path / "objects")
    key = "user/object.bin"
    path = tmp_path / "objects" / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"pdf-bytes")
    row = StorageDeletion(storage_key=key, status="pending", max_attempts=8, next_attempt_at=utc_now())
    pg_session.add(row)
    pg_session.commit()
    deletion_id = row.id
    barrier = threading.Barrier(2)
    deleted: list[int] = []
    errors: list[BaseException] = []

    def worker() -> None:
        session = pg_session_factory()
        try:
            service = DocumentService(session, storage, settings)
            barrier.wait(timeout=5)
            result = service.retry_storage_deletions()
            deleted.append(result["deleted"])
        except Exception as exc:
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert errors == []
    assert sum(deleted) == 1
    pg_session.expire_all()
    stored = pg_session.get(StorageDeletion, deletion_id)
    assert stored is not None
    assert stored.status == "completed"
    assert storage.exists(key) is False


def test_postgres_cleanup_recovers_stranded_failed_job(pg_session: Session, tmp_path: Path) -> None:
    user = _user(pg_session)
    credits = CreditService(pg_session)
    credits.ensure_account(user)
    job = Job(
        user_id=user.id,
        operation="extract_text",
        status="failed",
        credits_reserved=3,
        error_code="timeout",
        completed_at=utc_now(),
    )
    pg_session.add(job)
    pg_session.commit()
    credits.reserve(user, 3, job_id=job.id)
    pg_session.commit()
    settings = Settings(
        env="test",
        secret_key="test-secret-key-please-change",
        cleanup_interval_seconds=0,
        cleanup_lease_minutes=5,
        job_stale_minutes=90,
        storage_local_path=str(tmp_path / "storage"),
    )
    storage = FilesystemStorage(tmp_path / "storage")
    stats = run_runtime_cleanup(pg_session, storage, settings)
    assert stats.skipped is False
    account = credits.ensure_account(user)
    assert account.reserved == 0
    assert account.balance == 20
    assert stats.refunded_credits == 3


def test_postgres_concurrent_cleanup_second_skips(
    pg_session: Session, pg_session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    settings = Settings(
        env="test",
        secret_key="test-secret-key-please-change",
        cleanup_interval_seconds=0,
        cleanup_lease_minutes=5,
        job_stale_minutes=90,
        storage_local_path=str(tmp_path / "storage"),
    )
    storage = FilesystemStorage(tmp_path / "storage")
    assert acquire_lease(pg_session, "holder") is True
    other = pg_session_factory()
    try:
        stats = run_runtime_cleanup(other, storage, settings)
        assert stats.skipped is True
        assert stats.abandoned_jobs == 0
        assert release_lease(other, "not-the-owner") is False
        pg_session.expire_all()
        row = pg_session.get(CleanupLease, LEASE_NAME)
        assert row is not None
        assert row.owner_token == "holder"
        assert release_lease(pg_session, "holder") is True
    finally:
        other.close()


def test_postgres_stale_deletion_finish_does_not_clobber_new_owner(
    pg_session: Session, pg_session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    settings = Settings(
        env="test",
        secret_key="test-secret-key-please-change",
        storage_delete_max_attempts=8,
        storage_delete_lease_minutes=5,
        cleanup_interval_seconds=0,
    )
    storage = FilesystemStorage(tmp_path / "objects")
    key = "user/race.bin"
    path = tmp_path / "objects" / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"pdf-bytes")
    row = StorageDeletion(
        storage_key=key,
        status="in_progress",
        attempts=1,
        max_attempts=8,
        owner_token="old-owner",
        lease_until=utc_now() + timedelta(minutes=5),
        next_attempt_at=utc_now(),
    )
    pg_session.add(row)
    pg_session.commit()
    deletion_id = row.id
    other = pg_session_factory()
    try:
        newer = DocumentService(other, storage, settings)
        claimed = other.execute(
            update(StorageDeletion)
            .where(StorageDeletion.id == deletion_id)
            .values(owner_token="new-owner", status="in_progress", lease_until=utc_now() + timedelta(minutes=5))
        )
        other.commit()
        assert int(getattr(claimed, "rowcount", 0) or 0) == 1
        stale = DocumentService(pg_session, storage, settings)
        assert stale._finish_owned_deletion(deletion_id, "old-owner", success=True) is False
        other.expire_all()
        stored = other.get(StorageDeletion, deletion_id)
        assert stored is not None
        assert stored.status == "in_progress"
        assert stored.owner_token == "new-owner"
        assert newer._finish_owned_deletion(deletion_id, "new-owner", success=True) is True
        other.expire_all()
        stored = other.get(StorageDeletion, deletion_id)
        assert stored is not None
        assert stored.status == "completed"
        assert stored.owner_token is None
    finally:
        other.close()
