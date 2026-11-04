from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from docuflow.billing.plans import DEFAULT_OPERATION_COSTS, DEFAULT_PLANS, PlanSeed
from docuflow.models import OperationCost, Plan, User
from docuflow.security.passwords import hash_password

# Catalog-only seed policy. User.plan_slug, credit accounts, and ledger rows are never
# written here. Plan limits may stay the same or increase; they never shrink.
# Feature flags are merged so a True entitlement cannot be flipped off by startup.


def seed_reference_data(session: Session) -> None:
    for item in DEFAULT_PLANS:
        existing = session.get(Plan, item["slug"])
        if existing is None:
            session.add(Plan(**item))
        else:
            _apply_safe_plan_update(existing, item)
    for operation, credits in DEFAULT_OPERATION_COSTS.items():
        if session.get(OperationCost, operation) is None:
            session.add(OperationCost(operation=operation, credits=credits, description=operation.replace("_", " ")))
    session.commit()


def _apply_safe_plan_update(existing: Plan, item: PlanSeed) -> None:
    existing.name = str(item["name"])
    existing.is_public = bool(item["is_public"])
    existing.monthly_credits = max(int(existing.monthly_credits), int(item["monthly_credits"]))
    existing.max_file_bytes = max(int(existing.max_file_bytes), int(item["max_file_bytes"]))
    existing.max_pages = max(int(existing.max_pages), int(item["max_pages"]))
    existing.max_ai_requests_per_day = max(int(existing.max_ai_requests_per_day), int(item["max_ai_requests_per_day"]))
    merged = dict(existing.features or {})
    for key, value in dict(item["features"]).items():
        if key not in merged:
            merged[key] = value
        elif value is True:
            merged[key] = True
    existing.features = merged


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
