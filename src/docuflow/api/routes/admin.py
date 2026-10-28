from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from docuflow.api.deps import get_db, require_admin
from docuflow.billing.ledger import CreditService
from docuflow.models import Job, OperationCost, Plan, User

router = APIRouter(prefix="/v1/admin", tags=["admin"])


class CreditAdjust(BaseModel):
    email: str
    amount: int = Field(gt=0)
    reason: str = Field(min_length=3, max_length=200)


class CostUpdate(BaseModel):
    operation: str
    credits: int = Field(ge=0)


@router.get("/overview")
def overview(admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    users = db.scalar(select(func.count()).select_from(User)) or 0
    jobs = db.scalar(select(func.count()).select_from(Job)) or 0
    failed = db.scalar(select(func.count()).select_from(Job).where(Job.status == "failed")) or 0
    return {"users": users, "jobs": jobs, "failed_jobs": failed, "admin": admin.email}


@router.get("/users")
def users(admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(User).order_by(User.created_at.desc()).limit(200))
    return [
        {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "plan_slug": user.plan_slug,
            "is_active": user.is_active,
        }
        for user in rows
    ]


@router.get("/jobs")
def jobs(admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Job).order_by(Job.created_at.desc()).limit(200))
    return [
        {
            "id": job.id,
            "user_id": job.user_id,
            "operation": job.operation,
            "status": job.status,
            "error_code": job.error_code,
        }
        for job in rows
    ]


@router.post("/credits")
def grant_credits(payload: CreditAdjust, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None:
        from docuflow.exceptions import NotFoundError

        raise NotFoundError("User not found.")
    CreditService(db).grant(
        user,
        payload.amount,
        reason=f"admin:{admin.id}:{payload.reason}",
        idempotency_key=f"admin-grant:{admin.id}:{user.id}:{payload.reason}:{payload.amount}",
    )
    db.commit()
    return {"ok": True}


@router.post("/operation-costs")
def update_cost(payload: CostUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    row = db.get(OperationCost, payload.operation)
    if row is None:
        row = OperationCost(operation=payload.operation, credits=payload.credits)
        db.add(row)
    else:
        row.credits = payload.credits
    db.commit()
    return {"ok": True, "operation": payload.operation, "credits": payload.credits}


@router.get("/plans")
def plans(admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    return [
        {
            "slug": plan.slug,
            "name": plan.name,
            "monthly_credits": plan.monthly_credits,
            "max_file_bytes": plan.max_file_bytes,
            "max_pages": plan.max_pages,
        }
        for plan in db.scalars(select(Plan))
    ]
