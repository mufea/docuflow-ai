from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from docuflow.billing.ledger import CreditService
from docuflow.config import Settings
from docuflow.db import Base
from docuflow.jobs.clock import as_utc, utc_now
from docuflow.jobs.heartbeat import ProcessingHeartbeat, touch_processing_heartbeat
from docuflow.jobs.refunds import fail_job_and_refund
from docuflow.jobs.retention import run_runtime_cleanup
from docuflow.jobs.runner import JobRunner
from docuflow.models import CreditLedger, Document, Job, Plan, User
from docuflow.security.passwords import hash_password
from docuflow.storage.filesystem import FilesystemStorage


def _factory(tmp_path: Path) -> sessionmaker[Session]:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'p104b.db'}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "env": "test",
        "secret_key": "test-secret-key-please-change",
        "database_url": f"sqlite+pysqlite:///{tmp_path / 'unused.db'}",
        "storage_backend": "filesystem",
        "storage_local_path": str(tmp_path / "storage"),
        "job_broker": "inline",
        "ai_provider": "mock",
        "job_stale_minutes": 90,
        "cleanup_interval_seconds": 0,
        "job_heartbeat_seconds": 60,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _seed(session: Session) -> User:
    session.add(
        Plan(
            slug="free",
            name="Free",
            monthly_credits=20,
            max_file_bytes=1_000_000,
            max_pages=10,
            max_ai_requests_per_day=2,
            features={},
        )
    )
    user = User(email="p104b@example.com", password_hash=hash_password("super-secret-1"), name="P104B")
    session.add(user)
    session.commit()
    CreditService(session).ensure_account(user)
    session.commit()
    return user


def _job(session: Session, user: User, *, status: str, reserved: int = 3) -> Job:
    job = Job(
        user_id=user.id,
        operation="extract_text",
        status=status,
        credits_reserved=reserved,
        started_at=datetime.now(UTC),
        heartbeat_at=datetime.now(UTC),
        input_document_ids=[],
    )
    session.add(job)
    session.commit()
    if reserved:
        CreditService(session).reserve(user, reserved, job_id=job.id)
        session.commit()
    return job


def _runner(tmp_path: Path, factory: sessionmaker[Session], settings: Settings | None = None) -> JobRunner:
    return JobRunner(
        session_factory=factory,
        storage=FilesystemStorage(tmp_path / "storage"),
        settings=settings or _settings(tmp_path),
        ai=MagicMock(),
    )


def test_heartbeat_updates_processing_job(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    try:
        user = _seed(session)
        job = _job(session, user, status="processing")
        before = job.heartbeat_at
        assert touch_processing_heartbeat(factory, job.id) is True
        session.refresh(job)
        assert job.status == "processing"
        assert job.heartbeat_at is not None
        assert before is not None
        assert as_utc(job.heartbeat_at) >= as_utc(before)
    finally:
        session.close()


def test_heartbeat_does_not_update_terminal_or_queued_jobs(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    try:
        user = _seed(session)
        for status in ("queued", "failed", "completed", "cancelled"):
            job = _job(session, user, status=status, reserved=0)
            stamped = datetime.now(UTC) - timedelta(hours=2)
            job.heartbeat_at = stamped
            session.commit()
            assert touch_processing_heartbeat(factory, job.id) is False
            session.refresh(job)
            assert job.status == status
            assert job.heartbeat_at is not None
            assert as_utc(job.heartbeat_at) == as_utc(stamped)
    finally:
        session.close()


def test_stale_fail_does_not_claim_after_fresh_heartbeat(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    try:
        user = _seed(session)
        job = _job(session, user, status="processing")
        cutoff = utc_now() - timedelta(minutes=90)
        job.heartbeat_at = cutoff - timedelta(minutes=5)
        job.started_at = cutoff - timedelta(minutes=5)
        session.commit()
        assert touch_processing_heartbeat(factory, job.id) is True
        result = fail_job_and_refund(
            session,
            job.id,
            code="timeout",
            message="stale",
            expected_statuses=("processing",),
            stale_before=cutoff,
            commit=True,
        )
        assert result.claimed is False
        session.refresh(job)
        assert job.status == "processing"
        refunds = list(session.query(CreditLedger).filter_by(idempotency_key=f"refund:{job.id}"))
        assert refunds == []
    finally:
        session.close()


def test_cleanup_fails_stale_heartbeat_and_refunds_once(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    storage = FilesystemStorage(tmp_path / "storage")
    try:
        user = _seed(session)
        job = _job(session, user, status="processing")
        job.heartbeat_at = datetime.now(UTC) - timedelta(hours=3)
        job.started_at = datetime.now(UTC) - timedelta(hours=3)
        session.commit()
        stats = run_runtime_cleanup(session, storage, _settings(tmp_path, job_stale_minutes=90))
        assert stats.abandoned_jobs == 1
        session.refresh(job)
        assert job.status == "failed"
        assert job.error_code == "timeout"
        refunds = list(session.query(CreditLedger).filter_by(idempotency_key=f"refund:{job.id}"))
        assert len(refunds) == 1
        second = run_runtime_cleanup(session, storage, _settings(tmp_path, job_stale_minutes=90))
        assert second.abandoned_jobs == 0
        refunds = list(session.query(CreditLedger).filter_by(idempotency_key=f"refund:{job.id}"))
        assert len(refunds) == 1
    finally:
        session.close()


def test_periodic_heartbeat_during_long_operation(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    try:
        user = _seed(session)
        job = _job(session, user, status="processing")
        job.heartbeat_at = datetime.now(UTC) - timedelta(minutes=10)
        session.commit()
        with ProcessingHeartbeat(factory, job.id, interval_seconds=0.05):
            time.sleep(0.2)
        session.refresh(job)
        assert job.status == "processing"
        assert job.heartbeat_at is not None
        age = datetime.now(UTC) - as_utc(job.heartbeat_at)
        assert age.total_seconds() < 2
    finally:
        session.close()


def test_lost_ownership_skips_result_persist_and_settle(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    runner = _runner(tmp_path, factory, _settings(tmp_path, job_heartbeat_seconds=0))
    stored: list[str] = []

    def fake_op(job: Job, inputs: list[Path], work: Path, password: str | None):
        other = factory()
        try:
            fail_job_and_refund(other, job.id, code="timeout", message="stale", commit=True)
        finally:
            other.close()
        dest = work / "should-not-store.txt"
        dest.write_text("leak")
        stored.append(dest.name)
        return [dest], {"text": "should-not-complete"}

    runner._run_operation = fake_op  # type: ignore[method-assign]
    try:
        user = _seed(session)
        job = _job(session, user, status="queued")
        job_id = job.id
        user_id = user.id
        runner.process(job_id)
        session.expire_all()
        stored_job = session.get(Job, job_id)
        assert stored_job is not None
        assert stored_job.status == "failed"
        assert stored_job.result_document_ids in (None, [])
        assert session.query(Document).filter_by(user_id=user_id).count() == 0
        assert session.query(CreditLedger).filter_by(idempotency_key=f"settle:{job_id}").first() is None
        refunds = list(session.query(CreditLedger).filter_by(idempotency_key=f"refund:{job_id}"))
        assert len(refunds) == 1
    finally:
        session.close()
