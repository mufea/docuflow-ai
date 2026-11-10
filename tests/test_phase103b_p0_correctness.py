from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from docuflow.billing.ledger import CreditService
from docuflow.config import Settings
from docuflow.db import Base
from docuflow.exceptions import ConflictError
from docuflow.jobs.completion import complete_job_if_processing
from docuflow.jobs.refunds import fail_job_and_refund
from docuflow.jobs.runner import JobRunner
from docuflow.models import CreditLedger, Job, Plan, User
from docuflow.security.passwords import hash_password
from docuflow.storage.filesystem import FilesystemStorage


def _factory(tmp_path: Path) -> sessionmaker[Session]:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'p0.db'}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


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
    user = User(email="p0@example.com", password_hash=hash_password("super-secret-1"), name="P0")
    session.add(user)
    session.commit()
    CreditService(session).ensure_account(user)
    session.commit()
    return user


def _job(session: Session, user: User, *, status: str, reserved: int = 4) -> Job:
    job = Job(
        user_id=user.id,
        operation="extract_text",
        status=status,
        credits_reserved=reserved,
    )
    session.add(job)
    session.commit()
    if reserved:
        CreditService(session).reserve(user, reserved, job_id=job.id)
        session.commit()
    return job


def _runner(tmp_path: Path, factory: sessionmaker[Session]) -> JobRunner:
    settings = Settings(
        env="test",
        secret_key="test-secret-key-please-change",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'unused.db'}",
        storage_backend="filesystem",
        storage_local_path=str(tmp_path / "storage"),
        job_broker="inline",
        ai_provider="mock",
    )
    return JobRunner(
        session_factory=factory,
        storage=FilesystemStorage(tmp_path / "storage"),
        settings=settings,
        ai=MagicMock(),
    )


def _ledger_keys(session: Session, job_id: str) -> set[str]:
    rows = session.query(CreditLedger).filter(CreditLedger.job_id == job_id).all()
    return {row.idempotency_key for row in rows}


def test_processing_job_can_be_completed(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    user = _seed(session)
    job = _job(session, user, status="processing")
    result = complete_job_if_processing(
        session,
        job.id,
        result_payload={"text": "ok"},
        result_document_ids=["doc-1"],
        commit=True,
    )
    session.refresh(job)
    assert result.claimed is True
    assert result.previous_status == "processing"
    assert job.status == "completed"
    assert job.progress == 100
    assert job.completed_at is not None
    assert job.result_payload == {"text": "ok"}
    assert job.result_document_ids == ["doc-1"]


@pytest.mark.parametrize("status", ["queued", "failed", "completed"])
def test_non_processing_job_cannot_be_completed(tmp_path: Path, status: str) -> None:
    factory = _factory(tmp_path)
    session = factory()
    user = _seed(session)
    job = _job(session, user, status=status, reserved=0)
    original_payload = dict(job.result_payload)
    result = complete_job_if_processing(
        session,
        job.id,
        result_payload={"text": "late"},
        commit=True,
    )
    session.refresh(job)
    assert result.claimed is False
    assert result.previous_status == status
    assert job.status == status
    assert job.result_payload == original_payload
    assert job.progress == 0
    assert job.completed_at is None or status == "completed"


def test_completed_job_cannot_complete_again(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    user = _seed(session)
    job = _job(session, user, status="processing", reserved=0)
    first = complete_job_if_processing(session, job.id, result_payload={"n": 1}, commit=True)
    second = complete_job_if_processing(session, job.id, result_payload={"n": 2}, commit=True)
    session.refresh(job)
    assert first.claimed is True
    assert second.claimed is False
    assert second.previous_status == "completed"
    assert job.status == "completed"
    assert job.result_payload == {"n": 1}


def test_missing_job_is_not_completed(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    _seed(session)
    result = complete_job_if_processing(session, "missing-job-id", result_payload={"n": 1}, commit=True)
    assert result.claimed is False
    assert result.previous_status is None
    assert session.get(Job, "missing-job-id") is None


def test_failed_job_complete_does_not_overwrite_failure(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    user = _seed(session)
    job = _job(session, user, status="processing")
    fail = fail_job_and_refund(session, job.id, code="timeout", message="stale", commit=True)
    result = complete_job_if_processing(session, job.id, result_payload={"late": True}, commit=True)
    session.refresh(job)
    assert fail.claimed is True
    assert result.claimed is False
    assert job.status == "failed"
    assert job.error_code == "timeout"
    assert job.result_payload == {}
    assert "settle:" + job.id not in _ledger_keys(session, job.id)
    assert f"refund:{job.id}" in _ledger_keys(session, job.id)


def test_runner_completes_and_settles_processing_job(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    user = _seed(session)
    job = _job(session, user, status="queued")
    runner = _runner(tmp_path, factory)
    runner._execute = lambda _session, _job, _user: {"text": "done"}  # type: ignore[method-assign]
    runner.process(job.id)
    session.refresh(job)
    account = CreditService(session).ensure_account(user)
    assert job.status == "completed"
    assert job.credits_settled == job.credits_reserved
    assert job.result_payload == {"text": "done"}
    assert account.reserved == 0
    assert account.balance == 16
    assert f"settle:{job.id}" in _ledger_keys(session, job.id)


def test_runner_does_not_settle_when_completion_loses(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    user = _seed(session)
    job = _job(session, user, status="queued")
    runner = _runner(tmp_path, factory)

    def fail_during_execute(work_session: Session, work_job: Job, _user: User) -> dict[str, str]:
        other = factory()
        try:
            fail_job_and_refund(
                other,
                work_job.id,
                code="timeout",
                message="stale cleanup",
                expected_statuses=("processing",),
                commit=True,
            )
        finally:
            other.close()
        return {"text": "late"}

    runner._execute = fail_during_execute  # type: ignore[method-assign]
    runner.process(job.id)
    session.expire_all()
    stored = session.get(Job, job.id)
    account = CreditService(session).ensure_account(user)
    assert stored is not None
    assert stored.status == "failed"
    assert stored.error_code == "timeout"
    assert stored.credits_settled == 0
    assert stored.result_payload == {}
    assert account.reserved == 0
    assert account.balance == 20
    keys = _ledger_keys(session, job.id)
    assert f"refund:{job.id}" in keys
    assert f"settle:{job.id}" not in keys


def test_settle_without_refund(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    user = _seed(session)
    job = _job(session, user, status="processing")
    CreditService(session).settle(user, 4, job_id=job.id)
    account = CreditService(session).ensure_account(user)
    assert account.reserved == 0
    assert account.balance == 16
    assert f"settle:{job.id}" in _ledger_keys(session, job.id)


def test_repeated_settle_is_idempotent(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    user = _seed(session)
    job = _job(session, user, status="processing")
    service = CreditService(session)
    service.settle(user, 4, job_id=job.id)
    service.settle(user, 4, job_id=job.id)
    account = service.ensure_account(user)
    settles = [row for row in session.query(CreditLedger).all() if row.idempotency_key == f"settle:{job.id}"]
    assert len(settles) == 1
    assert account.reserved == 0
    assert account.balance == 16


def test_settle_refused_when_refund_exists(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    user = _seed(session)
    job = _job(session, user, status="processing")
    service = CreditService(session)
    refund = service.refund_reservation(user, 4, job_id=job.id)
    account_before = service.ensure_account(user)
    reserved_before = account_before.reserved
    balance_before = account_before.balance
    refund_row = session.query(CreditLedger).filter_by(idempotency_key=f"refund:{job.id}").one()
    with pytest.raises(ConflictError) as exc_info:
        service.settle(user, 4, job_id=job.id)
    session.rollback()
    account = service.ensure_account(user)
    keys = [row.idempotency_key for row in session.query(CreditLedger).all() if row.job_id == job.id]
    assert refund.released == 4
    assert exc_info.value.code == "conflict"
    assert exc_info.value.details == {"job_id": job.id, "reason": "already_refunded"}
    assert account.reserved == reserved_before == 0
    assert account.balance == balance_before == 20
    assert f"settle:{job.id}" not in keys
    assert f"release-settle:{job.id}" not in keys
    assert f"refund:{job.id}" in keys
    still = session.query(CreditLedger).filter_by(idempotency_key=f"refund:{job.id}").one()
    assert still.id == refund_row.id
    assert still.amount == refund_row.amount


def test_refund_remains_idempotent_after_refused_settle(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    user = _seed(session)
    job = _job(session, user, status="processing")
    service = CreditService(session)
    service.refund_reservation(user, 4, job_id=job.id)
    with pytest.raises(ConflictError):
        service.settle(user, 4, job_id=job.id)
    session.rollback()
    again = service.refund_reservation(user, 4, job_id=job.id)
    refunds = [row for row in session.query(CreditLedger).all() if row.idempotency_key == f"refund:{job.id}"]
    assert again.already_refunded is True
    assert again.released == 0
    assert len(refunds) == 1


def test_settle_does_not_swallow_database_errors(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    user = _seed(session)
    job = _job(session, user, status="processing")
    service = CreditService(session)
    original_flush = session.flush

    def boom_flush(*args: object, **kwargs: object) -> None:
        raise OperationalError("INSERT", {}, Exception("connection lost"))

    session.flush = boom_flush  # type: ignore[method-assign]
    with pytest.raises(OperationalError):
        service.settle(user, 4, job_id=job.id)
    session.flush = original_flush  # type: ignore[method-assign]
    session.rollback()
    account = CreditService(session).ensure_account(user)
    assert account.reserved == 4
    assert account.balance == 20
    assert session.query(CreditLedger).filter_by(idempotency_key=f"settle:{job.id}").first() is None
