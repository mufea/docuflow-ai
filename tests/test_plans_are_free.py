from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from docuflow.db import Base
from docuflow.models import Plan, User
from docuflow.security.passwords import hash_password
from docuflow.services.seed import seed_reference_data


def test_public_catalog_is_free_only(client: TestClient) -> None:
    plans = client.get("/v1/billing/plans").json()
    assert [plan["slug"] for plan in plans] == ["free"]


def test_seed_moves_existing_users_to_free(tmp_path) -> None:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'plans.db'}", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    session.add(
        Plan(
            slug="pro",
            name="Pro",
            monthly_credits=500,
            max_file_bytes=1_000_000,
            max_pages=10,
            max_ai_requests_per_day=2,
            features={},
            is_public=True,
        )
    )
    session.add(
        User(
            email="paid@example.com",
            password_hash=hash_password("super-secret-1"),
            name="Paid",
            plan_slug="pro",
        )
    )
    session.commit()
    seed_reference_data(session)
    user = session.query(User).filter_by(email="paid@example.com").one()
    assert user.plan_slug == "free"
    pro = session.get(Plan, "pro")
    assert pro is not None
    assert pro.is_public is False
    free = session.get(Plan, "free")
    assert free is not None
    assert free.is_public is True
