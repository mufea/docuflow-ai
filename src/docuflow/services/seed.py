from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from docuflow.billing.plans import DEFAULT_OPERATION_COSTS, DEFAULT_PLANS
from docuflow.models import OperationCost, Plan, User
from docuflow.security.passwords import hash_password


def seed_reference_data(session: Session) -> None:
    for item in DEFAULT_PLANS:
        if session.get(Plan, item["slug"]) is None:
            session.add(Plan(**item))
    for operation, credits in DEFAULT_OPERATION_COSTS.items():
        if session.get(OperationCost, operation) is None:
            session.add(OperationCost(operation=operation, credits=credits, description=operation.replace("_", " ")))
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
        plan_slug="business",
        is_active=True,
    )
    session.add(user)
    session.commit()
