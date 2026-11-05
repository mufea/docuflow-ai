from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from docuflow.billing.ledger import CreditService
from docuflow.db import Base
from docuflow.exceptions import InsufficientCreditsError
from docuflow.jobs.refunds import fail_job_and_refund
from docuflow.jobs.retention import run_runtime_cleanup
from docuflow.models import CreditLedger, Job, Plan, User
from docuflow.security.passwords import hash_password
from tests.conftest import register_and_login
from tests.pdf.conftest import write_text_pdf
from tests.test_jobs_and_security import _upload


def _session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'credits.db'}", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
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
    session.add(User(email="ledger@example.com", password_hash=hash_password("super-secret-1"), name="Ledger"))
    session.commit()
    return session


def _user(session: Session) -> User:
    return session.query(User).one()


def test_successful_refund_releases_reserved_credits(tmp_path: Path) -> None:
    session = _session(tmp_path)
    user = _user(session)
    service = CreditService(session)
    service.ensure_account(user)
    service.reserve(user, 5, job_id="job-ok")
    result = service.refund_reservation(user, 5, job_id="job-ok")
    account = service.ensure_account(user)
    assert result.released == 5
    assert result.already_refunded is False
    assert account.reserved == 0
    assert account.balance == 20
    keys = [row.idempotency_key for row in session.query(CreditLedger).all()]
    assert "refund:job-ok" in keys


def test_duplicate_refund_is_idempotent(tmp_path: Path) -> None:
    session = _session(tmp_path)
    user = _user(session)
    service = CreditService(session)
    service.ensure_account(user)
    service.reserve(user, 4, job_id="job-dup")
    first = service.refund_reservation(user, 4, job_id="job-dup")
    second = service.refund_reservation(user, 4, job_id="job-dup")
    account = service.ensure_account(user)
    assert first.released == 4
    assert second.already_refunded is True
    assert second.released == 0
    assert account.reserved == 0
    assert account.balance == 20
    refunds = [row for row in session.query(CreditLedger).all() if row.idempotency_key == "refund:job-dup"]
    assert len(refunds) == 1


def test_refund_with_insufficient_reserved_balance(tmp_path: Path) -> None:
    session = _session(tmp_path)
    user = _user(session)
    service = CreditService(session)
    service.ensure_account(user)
    service.reserve(user, 2, job_id="job-partial")
    result = service.refund_reservation(user, 9, job_id="job-partial")
    account = service.ensure_account(user)
    assert result.released == 2
    assert account.reserved == 0
    assert account.balance == 20


def test_refund_missing_reservation_is_safe(tmp_path: Path) -> None:
    session = _session(tmp_path)
    user = _user(session)
    service = CreditService(session)
    service.ensure_account(user)
    result = service.refund_reservation(user, 3, job_id="job-missing")
    account = service.ensure_account(user)
    assert result.released == 0
    assert result.missing_reservation is True
    assert account.reserved == 0
    assert account.balance == 20
    again = service.refund_reservation(user, 3, job_id="job-missing")
    assert again.already_refunded is True


def test_refund_does_not_run_after_settle(tmp_path: Path) -> None:
    session = _session(tmp_path)
    user = _user(session)
    service = CreditService(session)
    service.ensure_account(user)
    service.reserve(user, 3, job_id="job-settled")
    service.settle(user, 3, job_id="job-settled")
    result = service.refund_reservation(user, 3, job_id="job-settled")
    account = service.ensure_account(user)
    assert result.settled is True
    assert result.released == 0
    assert account.reserved == 0
    assert account.balance == 17


def test_reserve_still_rejects_insufficient_credits(tmp_path: Path) -> None:
    session = _session(tmp_path)
    user = _user(session)
    service = CreditService(session)
    service.ensure_account(user)
    try:
        service.reserve(user, 500, job_id="too-big")
        raise AssertionError("expected insufficient credits")
    except InsufficientCreditsError:
        pass
    assert service.ensure_account(user).reserved == 0


def _processing_job(session: Session, user: User, *, reserved: int = 5) -> Job:
    job = Job(
        user_id=user.id,
        operation="extract_text",
        status="processing",
        credits_reserved=reserved,
        started_at=datetime.now(UTC),
        heartbeat_at=datetime.now(UTC),
    )
    session.add(job)
    session.commit()
    CreditService(session).reserve(user, reserved, job_id=job.id)
    session.commit()
    return job


def test_job_failure_and_refund_are_atomic(tmp_path: Path) -> None:
    session = _session(tmp_path)
    user = _user(session)
    CreditService(session).ensure_account(user)
    job = _processing_job(session, user, reserved=5)
    result = fail_job_and_refund(
        session,
        job.id,
        code="timeout",
        message="failed together",
        commit=True,
    )
    session.refresh(job)
    account = CreditService(session).ensure_account(user)
    assert result.claimed is True
    assert result.refund is not None
    assert result.refund.released == 5
    assert job.status == "failed"
    assert account.reserved == 0
    assert account.balance == 20


def test_job_failure_rollback_restores_job_and_credits(tmp_path: Path) -> None:
    session = _session(tmp_path)
    user = _user(session)
    CreditService(session).ensure_account(user)
    job = _processing_job(session, user, reserved=5)
    result = fail_job_and_refund(
        session,
        job.id,
        code="timeout",
        message="should roll back",
        commit=False,
    )
    assert result.claimed is True
    session.rollback()
    session.refresh(job)
    account = CreditService(session).ensure_account(user)
    assert job.status == "processing"
    assert account.reserved == 5
    assert account.balance == 20
    assert session.query(CreditLedger).filter_by(idempotency_key=f"refund:{job.id}").first() is None


def test_expired_job_cleanup_then_retry_does_not_double_refund(client: TestClient, app, tmp_path: Path) -> None:
    auth = register_and_login(client)
    before = client.get("/v1/billing/usage").json()
    doc_id = _upload(client, write_text_pdf(tmp_path / "stale.pdf", ["stale"]), auth["csrf"])
    app.state.ctx.broker.enqueue = lambda _job_id: None  # type: ignore[method-assign]
    created = client.post(
        "/v1/jobs",
        json={"operation": "extract_text", "document_ids": [doc_id], "params": {}},
        headers={"X-CSRF-Token": auth["csrf"], "Origin": "http://testserver"},
    )
    job_id = created.json()["id"]
    db = app.state.ctx.session_factory()
    try:
        job = db.get(Job, job_id)
        assert job is not None
        job.status = "processing"
        job.started_at = datetime.now(UTC) - timedelta(hours=3)
        job.heartbeat_at = datetime.now(UTC) - timedelta(hours=3)
        db.commit()
        first = run_runtime_cleanup(db, app.state.ctx.storage, app.state.ctx.settings)
        second = run_runtime_cleanup(db, app.state.ctx.storage, app.state.ctx.settings)
        assert first.abandoned_jobs == 1
        assert first.refunded_credits >= 1
        assert second.abandoned_jobs == 0
        stored = db.get(Job, job_id)
        assert stored is not None
        assert stored.status == "failed"
        refunds = list(db.query(CreditLedger).filter_by(idempotency_key=f"refund:{job_id}"))
        assert len(refunds) == 1
    finally:
        db.close()
    app.state.ctx.runner.process(job_id)
    after = client.get("/v1/billing/usage").json()
    assert after["available"] == before["available"]
    assert after["reserved"] == 0
    assert client.get(f"/v1/jobs/{job_id}").json()["status"] == "failed"
