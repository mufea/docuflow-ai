from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from docuflow.billing.plans import DEFAULT_OPERATION_COSTS, DEFAULT_PLANS
from docuflow.models import OperationCost, Plan, User
from docuflow.security.passwords import hash_password


def seed_reference_data(session: Session) -> None:
    for item in DEFAULT_PLANS:
        existing = session.get(Plan, item["slug"])
        if existing is None:
            session.add(Plan(**item))
        else:
            existing.is_public = bool(item["is_public"])
            existing.name = str(item["name"])
            existing.monthly_credits = int(item["monthly_credits"])
            existing.max_file_bytes = int(item["max_file_bytes"])
            existing.max_pages = int(item["max_pages"])
            existing.max_ai_requests_per_day = int(item["max_ai_requests_per_day"])
            existing.features = dict(item["features"])
    for operation, credits in DEFAULT_OPERATION_COSTS.items():
        if session.get(OperationCost, operation) is None:
            session.add(OperationCost(operation=operation, credits=credits, description=operation.replace("_", " ")))
    session.execute(update(User).where(User.plan_slug != "free").values(plan_slug="free"))
    session.commit()


def ensure_demo_admin(session: Session) -> None:
    existing = session.scalar(select(User).where(User.email == "admin@docuflow.test"))
    if existing:
        return
    user = User(
        email="admin@docuflow.test",
        password_hash=hash_password("ChangeMeNow!!"),
        name="Administrator",
        role="admin",
        plan_slug="free",
        is_active=True,
    )
    session.add(user)
    session.commit()
