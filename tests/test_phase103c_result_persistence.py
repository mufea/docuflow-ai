from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from docuflow.billing.ledger import CreditService
from docuflow.config import Settings
from docuflow.db import Base
from docuflow.exceptions import ConflictError
from docuflow.jobs.refunds import fail_job_and_refund
from docuflow.jobs.runner import JobRunner
from docuflow.models import CreditLedger, Document, Job, Plan, User
from docuflow.security.passwords import hash_password
from docuflow.services.documents import DocumentService
from docuflow.storage.filesystem import FilesystemStorage
from tests.pdf.conftest import write_text_pdf


def _factory(tmp_path: Path) -> sessionmaker[Session]:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'p03c.db'}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        env="test",
        secret_key="test-secret-key-please-change",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'unused.db'}",
        storage_backend="filesystem",
        storage_local_path=str(tmp_path / "storage"),
        job_broker="inline",
        ai_provider="mock",
    )


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
    user = User(email="p03c@example.com", password_hash=hash_password("super-secret-1"), name="P03C")
    session.add(user)
    session.commit()
    CreditService(session).ensure_account(user)
    session.commit()
    return user


def _service(session: Session, tmp_path: Path) -> DocumentService:
    return DocumentService(session, FilesystemStorage(tmp_path / "storage"), _settings(tmp_path))


def _pdf(tmp_path: Path, name: str = "doc.pdf") -> Path:
    return write_text_pdf(tmp_path / name, ["phase-10-3c"])


def _queued_job(session: Session, user: User, *, reserved: int = 3) -> Job:
    job = Job(
        user_id=user.id,
        operation="extract_text",
        status="queued",
        credits_reserved=reserved,
        input_document_ids=[],
    )
    session.add(job)
    session.commit()
    CreditService(session).reserve(user, reserved, job_id=job.id)
    session.commit()
    return job


def _runner(tmp_path: Path, factory: sessionmaker[Session], storage: FilesystemStorage | None = None) -> JobRunner:
    settings = _settings(tmp_path)
    return JobRunner(
        session_factory=factory,
        storage=storage or FilesystemStorage(tmp_path / "storage"),
        settings=settings,
        ai=MagicMock(),
    )


def _copy_outputs(inputs: list[Path], work: Path, names: list[str]) -> tuple[list[Path], dict[str, str]]:
    outputs: list[Path] = []
    for name in names:
        dest = work / name
        shutil.copyfile(inputs[0], dest)
        outputs.append(dest)
    return outputs, {"engine": "test"}


def test_store_upload_commits_immediately(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    user = _seed(session)
    stored = _service(session, tmp_path).store_upload(user, _pdf(tmp_path), "in.pdf")
    other = factory()
    try:
        visible = other.get(Document, stored.id)
        assert visible is not None
        assert visible.origin == "upload"
    finally:
        other.close()


def test_store_result_default_still_commits(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    user = _seed(session)
    stored = _service(session, tmp_path).store_result(user, _pdf(tmp_path), "out.pdf", origin="job:extract_text")
    other = factory()
    try:
        assert other.get(Document, stored.id) is not None
    finally:
        other.close()


def test_store_result_can_defer_commit(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    user = _seed(session)
    stored = _service(session, tmp_path).store_result(
        user, _pdf(tmp_path), "out.pdf", origin="job:extract_text", commit=False
    )
    assert stored.id
    other = factory()
    try:
        assert other.get(Document, stored.id) is None
        session.commit()
        other.expire_all()
        assert other.get(Document, stored.id) is not None
    finally:
        other.close()


def test_deferred_result_rollback_removes_document_row(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    user = _seed(session)
    stored = _service(session, tmp_path).store_result(
        user, _pdf(tmp_path), "out.pdf", origin="job:extract_text", commit=False
    )
    doc_id = stored.id
    key = stored.storage_key
    storage = FilesystemStorage(tmp_path / "storage")
    session.rollback()
    other = factory()
    try:
        assert other.get(Document, doc_id) is None
        assert storage.exists(key) is True
    finally:
        other.close()


def test_successful_job_persists_result_documents_with_completion(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    user = _seed(session)
    settings = _settings(tmp_path)
    storage = FilesystemStorage(tmp_path / "storage")
    uploaded = DocumentService(session, storage, settings).store_upload(user, _pdf(tmp_path, "in.pdf"), "in.pdf")
    job = _queued_job(session, user)
    job.input_document_ids = [uploaded.id]
    session.commit()
    runner = _runner(tmp_path, factory, storage)

    def fake_op(_job: Job, inputs: list[Path], work: Path, _password: str | None) -> tuple[list[Path], dict[str, str]]:
        return _copy_outputs(inputs, work, ["out.pdf"])

    runner._run_operation = fake_op  # type: ignore[method-assign]
    runner.process(job.id)
    other = factory()
    try:
        stored_job = other.get(Job, job.id)
        assert stored_job is not None
        assert stored_job.status == "completed"
        assert len(stored_job.result_document_ids) == 1
        result = other.get(Document, stored_job.result_document_ids[0])
        assert result is not None
        assert result.origin == "job:extract_text"
        assert stored_job.credits_settled == stored_job.credits_reserved
        assert other.query(CreditLedger).filter_by(idempotency_key=f"settle:{job.id}").one()
    finally:
        other.close()


def test_lost_completion_rolls_back_result_documents_and_does_not_settle(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    user = _seed(session)
    job = _queued_job(session, user)
    runner = _runner(tmp_path, factory)
    stored_ids: list[str] = []

    def store_then_lose(work_session: Session, work_job: Job, work_user: User) -> dict[str, str]:
        stored = DocumentService(work_session, runner.storage, runner.settings).store_result(
            work_user,
            _pdf(tmp_path, "late.pdf"),
            "late.pdf",
            origin="job:extract_text",
            commit=False,
        )
        stored_ids.append(stored.id)
        work_job.result_document_ids = [stored.id]
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
        return {"result_files": [stored.original_filename]}

    runner._execute = store_then_lose  # type: ignore[method-assign]
    runner.process(job.id)
    other = factory()
    try:
        stored_job = other.get(Job, job.id)
        assert stored_job is not None
        assert stored_job.status == "failed"
        assert stored_ids
        assert other.get(Document, stored_ids[0]) is None
        assert other.query(CreditLedger).filter_by(idempotency_key=f"settle:{job.id}").first() is None
        assert other.query(CreditLedger).filter_by(idempotency_key=f"refund:{job.id}").one()
    finally:
        other.close()


def test_settlement_failure_rolls_back_result_documents_and_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = _factory(tmp_path)
    session = factory()
    user = _seed(session)
    settings = _settings(tmp_path)
    storage = FilesystemStorage(tmp_path / "storage")
    uploaded = DocumentService(session, storage, settings).store_upload(user, _pdf(tmp_path, "in.pdf"), "in.pdf")
    job = _queued_job(session, user)
    job.input_document_ids = [uploaded.id]
    session.commit()
    runner = _runner(tmp_path, factory, storage)

    def fake_op(_job: Job, inputs: list[Path], work: Path, _password: str | None) -> tuple[list[Path], dict[str, str]]:
        return _copy_outputs(inputs, work, ["out.pdf"])

    def boom(_self: CreditService, _user: User, _amount: int, *, job_id: str) -> None:
        raise ConflictError("forced settlement failure", details={"job_id": job_id, "reason": "test"})

    runner._run_operation = fake_op  # type: ignore[method-assign]
    monkeypatch.setattr(CreditService, "settle", boom)
    runner.process(job.id)
    other = factory()
    try:
        stored_job = other.get(Job, job.id)
        assert stored_job is not None
        assert stored_job.status == "failed"
        assert stored_job.result_document_ids == []
        results = other.query(Document).filter(Document.origin == "job:extract_text").all()
        assert results == []
        assert other.query(CreditLedger).filter_by(idempotency_key=f"settle:{job.id}").first() is None
        assert other.query(CreditLedger).filter_by(idempotency_key=f"refund:{job.id}").one()
    finally:
        other.close()


class _FailSecondPut:
    def __init__(self, inner: FilesystemStorage) -> None:
        self.inner = inner
        self.keys: list[str] = []

    def __getattr__(self, name: str):
        return getattr(self.inner, name)

    def put(self, key: str, source: Path, content_type: str):
        if self.keys:
            raise RuntimeError("second output put failed")
        self.keys.append(key)
        return self.inner.put(key, source, content_type)


def test_partial_output_failure_does_not_commit_result_rows(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    session = factory()
    user = _seed(session)
    settings = _settings(tmp_path)
    inner = FilesystemStorage(tmp_path / "storage")
    storage = _FailSecondPut(inner)
    uploaded = DocumentService(session, inner, settings).store_upload(user, _pdf(tmp_path, "in.pdf"), "in.pdf")
    job = _queued_job(session, user)
    job.input_document_ids = [uploaded.id]
    session.commit()
    runner = _runner(tmp_path, factory, storage)  # type: ignore[arg-type]

    def fake_op(_job: Job, inputs: list[Path], work: Path, _password: str | None) -> tuple[list[Path], dict[str, str]]:
        return _copy_outputs(inputs, work, ["a.pdf", "b.pdf"])

    runner._run_operation = fake_op  # type: ignore[method-assign]
    runner.process(job.id)
    other = factory()
    try:
        stored_job = other.get(Job, job.id)
        assert stored_job is not None
        assert stored_job.status == "failed"
        assert other.query(Document).filter(Document.origin == "job:extract_text").all() == []
        assert storage.keys
        assert inner.exists(storage.keys[0]) is True
        assert other.query(CreditLedger).filter_by(idempotency_key=f"settle:{job.id}").first() is None
    finally:
        other.close()
