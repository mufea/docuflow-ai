from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from docuflow.billing.ledger import CreditService
from docuflow.config import Settings, reset_settings
from docuflow.jobs.retention import cleanup_abandoned_jobs
from docuflow.main import create_app
from docuflow.models import CreditLedger, Job, Subscription, User
from docuflow.security.passwords import hash_password
from tests.conftest import register_and_login
from tests.pdf.conftest import write_text_pdf
from tests.test_jobs_and_security import _upload, _wait_job


def _persistent_settings(tmp_path: Path) -> Settings:
    reset_settings()
    return Settings(
        env="test",
        secret_key="test-secret-key-please-change",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'persist.db'}",
        storage_backend="filesystem",
        storage_local_path=str(tmp_path / "storage"),
        job_broker="inline",
        ai_provider="mock",
        cookie_secure=False,
        cors_origins="http://testserver",
        stripe_webhook_secret="whsec_test",
        midtrans_server_key="midtrans-test",
        public_web_url="http://testserver",
    )


def test_repeated_app_startup_keeps_paid_plans_and_credits(tmp_path: Path) -> None:
    settings = _persistent_settings(tmp_path)
    app = create_app(settings)
    session = app.state.ctx.session_factory()
    try:
        pro = User(
            email="keep-pro@example.com",
            password_hash=hash_password("super-secret-1"),
            name="Keep Pro",
            plan_slug="pro",
        )
        business = User(
            email="keep-biz@example.com",
            password_hash=hash_password("super-secret-1"),
            name="Keep Business",
            plan_slug="business",
        )
        session.add_all([pro, business])
        session.commit()
        credits = CreditService(session)
        credits.ensure_account(pro)
        credits.grant(pro, 25, reason="startup bonus", idempotency_key="startup-bonus")
        session.commit()
        pro_id = pro.id
        biz_id = business.id
        balance = credits.ensure_account(pro).balance
        ledger_count = session.query(CreditLedger).filter_by(user_id=pro_id).count()
    finally:
        session.close()

    reset_settings()
    app = create_app(settings)
    reset_settings()
    app = create_app(settings)
    session = app.state.ctx.session_factory()
    try:
        assert session.get(User, pro_id).plan_slug == "pro"
        assert session.get(User, biz_id).plan_slug == "business"
        assert CreditService(session).ensure_account(session.get(User, pro_id)).balance == balance
        assert session.query(CreditLedger).filter_by(user_id=pro_id).count() == ledger_count
    finally:
        session.close()


def test_failed_job_refunds_reserved_credits(client: TestClient, tmp_path: Path) -> None:
    session = register_and_login(client)
    before = client.get("/v1/billing/usage").json()["available"]
    doc_id = _upload(client, write_text_pdf(tmp_path / "one.pdf", ["only page one"]), session["csrf"])
    created = client.post(
        "/v1/jobs",
        json={"operation": "extract", "document_ids": [doc_id], "params": {"pages": [99]}},
        headers={"X-CSRF-Token": session["csrf"], "Origin": "http://testserver"},
    )
    assert created.status_code == 200, created.text
    job = _wait_job(client, created.json()["id"])
    assert job["status"] == "failed"
    after = client.get("/v1/billing/usage").json()
    assert after["available"] == before
    assert after["reserved"] == 0


def test_cancelled_queued_job_refunds_credits(client: TestClient, app, tmp_path: Path) -> None:
    session = register_and_login(client)
    before = client.get("/v1/billing/usage").json()["available"]
    doc_id = _upload(client, write_text_pdf(tmp_path / "hold.pdf", ["hold"]), session["csrf"])

    def freeze(_job_id: str) -> None:
        return None

    app.state.ctx.broker.enqueue = freeze  # type: ignore[method-assign]
    created = client.post(
        "/v1/jobs",
        json={"operation": "extract_text", "document_ids": [doc_id], "params": {}},
        headers={"X-CSRF-Token": session["csrf"], "Origin": "http://testserver"},
    )
    assert created.status_code == 200, created.text
    job_id = created.json()["id"]
    reserved = client.get("/v1/billing/usage").json()
    assert reserved["reserved"] >= 1
    cancelled = client.post(
        f"/v1/jobs/{job_id}/cancel",
        headers={"X-CSRF-Token": session["csrf"], "Origin": "http://testserver"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    after = client.get("/v1/billing/usage").json()
    assert after["available"] == before
    assert after["reserved"] == 0


def test_abandoned_processing_job_refunds_credits(client: TestClient, app, tmp_path: Path) -> None:
    session = register_and_login(client)
    before = client.get("/v1/billing/usage").json()["available"]
    doc_id = _upload(client, write_text_pdf(tmp_path / "stuck.pdf", ["stuck"]), session["csrf"])
    app.state.ctx.broker.enqueue = lambda _job_id: None  # type: ignore[method-assign]
    created = client.post(
        "/v1/jobs",
        json={"operation": "extract_text", "document_ids": [doc_id], "params": {}},
        headers={"X-CSRF-Token": session["csrf"], "Origin": "http://testserver"},
    )
    job_id = created.json()["id"]
    db = app.state.ctx.session_factory()
    try:
        job = db.get(Job, job_id)
        assert job is not None
        job.status = "processing"
        job.started_at = datetime.now(UTC) - timedelta(hours=2)
        db.commit()
        cleanup_abandoned_jobs(db, stale_minutes=45)
    finally:
        db.close()
    job = client.get(f"/v1/jobs/{job_id}").json()
    assert job["status"] == "failed"
    assert job["error_code"] == "timeout"
    after = client.get("/v1/billing/usage").json()
    assert after["available"] == before
    assert after["reserved"] == 0


def test_cross_user_job_access_denied(client: TestClient, tmp_path: Path) -> None:
    first = register_and_login(client, "owner@example.com")
    doc_id = _upload(client, write_text_pdf(tmp_path / "owned.pdf", ["owned"]), first["csrf"])
    created = client.post(
        "/v1/jobs",
        json={"operation": "extract_text", "document_ids": [doc_id], "params": {}},
        headers={"X-CSRF-Token": first["csrf"], "Origin": "http://testserver"},
    )
    job_id = created.json()["id"]
    _wait_job(client, job_id)
    client.post("/v1/auth/logout")
    register_and_login(client, "other@example.com")
    denied = client.get(f"/v1/jobs/{job_id}")
    assert denied.status_code == 403


def test_completed_job_records_settled_credits(client: TestClient, app, tmp_path: Path) -> None:
    session = register_and_login(client)
    doc_id = _upload(client, write_text_pdf(tmp_path / "ok.pdf", ["ok"]), session["csrf"])
    created = client.post(
        "/v1/jobs",
        json={"operation": "extract_text", "document_ids": [doc_id], "params": {}},
        headers={"X-CSRF-Token": session["csrf"], "Origin": "http://testserver"},
    )
    job = _wait_job(client, created.json()["id"])
    assert job["status"] == "completed"
    assert job["credits_reserved"] == 1
    db = app.state.ctx.session_factory()
    try:
        stored = db.get(Job, job["id"])
        assert stored is not None
        assert stored.credits_settled == stored.credits_reserved == 1
    finally:
        db.close()


def test_second_subscription_event_upserts_instead_of_inserting(client: TestClient, app) -> None:
    register_and_login(client, "sub@example.com")
    import hashlib
    import hmac
    import json
    import time

    def post_event(event_id: str, event_type: str, extra: dict) -> None:
        payload = {"id": event_id, "type": event_type, "data": {"object": extra}}
        body = json.dumps(payload).encode()
        timestamp = str(int(time.time()))
        signature = hmac.new(b"whsec_test", f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
        response = client.post(
            "/v1/webhooks/stripe",
            content=body,
            headers={"stripe-signature": f"t={timestamp},v1={signature}"},
        )
        assert response.status_code == 200, response.text

    post_event(
        "evt_sub_1",
        "checkout.session.completed",
        {
            "customer_email": "sub@example.com",
            "status": "complete",
            "metadata": {"plan_slug": "pro", "credits": 500},
            "subscription": "sub_shared",
        },
    )
    post_event(
        "evt_sub_2",
        "customer.subscription.updated",
        {
            "id": "sub_shared",
            "customer_email": "sub@example.com",
            "status": "active",
            "metadata": {"plan_slug": "pro"},
        },
    )
    db = app.state.ctx.session_factory()
    try:
        user = db.scalar(select(User).where(User.email == "sub@example.com"))
        assert user is not None
        rows = list(db.scalars(select(Subscription).where(Subscription.user_id == user.id)))
        assert len(rows) == 1
        assert rows[0].provider_subscription_id == "sub_shared"
        assert user.plan_slug == "pro"
    finally:
        db.close()
