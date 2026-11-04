from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from docuflow.billing.ledger import CreditService
from docuflow.db import Base
from docuflow.models import CreditLedger, Plan, User
from docuflow.security.passwords import hash_password
from docuflow.services.seed import seed_reference_data


def test_public_catalog_is_free_only(client: TestClient) -> None:
    plans = client.get("/v1/billing/plans").json()
    assert [plan["slug"] for plan in plans] == ["free"]


def _seeded_session(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'plans.db'}", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    seed_reference_data(session)
    return session


def test_seed_does_not_downgrade_pro_or_business_users(tmp_path) -> None:
    session = _seeded_session(tmp_path)
    pro_user = User(
        email="pro@example.com",
        password_hash=hash_password("super-secret-1"),
        name="Pro User",
        plan_slug="pro",
    )
    business_user = User(
        email="biz@example.com",
        password_hash=hash_password("super-secret-1"),
        name="Business User",
        plan_slug="business",
    )
    session.add_all([pro_user, business_user])
    session.commit()
    CreditService(session).ensure_account(pro_user)
    CreditService(session).grant(pro_user, 17, reason="manual bonus", idempotency_key="bonus-pro")
    session.commit()
    pro_balance = CreditService(session).ensure_account(pro_user).balance
    ledger_ids = [row.id for row in session.query(CreditLedger).filter_by(user_id=pro_user.id).all()]

    seed_reference_data(session)
    seed_reference_data(session)

    assert session.query(User).filter_by(email="pro@example.com").one().plan_slug == "pro"
    assert session.query(User).filter_by(email="biz@example.com").one().plan_slug == "business"
    account = CreditService(session).ensure_account(pro_user)
    assert account.balance == pro_balance
    assert [row.id for row in session.query(CreditLedger).filter_by(user_id=pro_user.id).all()] == ledger_ids
    pro = session.get(Plan, "pro")
    assert pro is not None
    assert pro.is_public is False
    assert session.get(Plan, "free") is not None
    assert session.get(Plan, "free").is_public is True


def test_seed_never_shrinks_existing_plan_limits(tmp_path) -> None:
    session = _seeded_session(tmp_path)
    pro = session.get(Plan, "pro")
    assert pro is not None
    pro.monthly_credits = 9000
    pro.max_pages = 800
    pro.features = {"ai": True, "ocr": True, "conversion": True, "priority": True, "custom": True}
    session.commit()
    seed_reference_data(session)
    pro = session.get(Plan, "pro")
    assert pro.monthly_credits == 9000
    assert pro.max_pages == 800
    assert pro.features.get("custom") is True
    assert pro.features.get("priority") is True
