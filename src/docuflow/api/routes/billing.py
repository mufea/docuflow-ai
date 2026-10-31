from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from docuflow.api.deps import get_db, require_user
from docuflow.api.schemas import LedgerOut, PlanOut
from docuflow.billing.ledger import CreditService
from docuflow.models import CreditLedger, OperationCost, Plan, User

router = APIRouter(prefix="/v1/billing", tags=["billing"])


@router.get("/plans", response_model=list[PlanOut])
def list_plans(db: Session = Depends(get_db)) -> list[PlanOut]:
    plans = db.scalars(select(Plan).where(Plan.is_public.is_(True)))
    return [
        PlanOut(
            slug=plan.slug,
            name=plan.name,
            monthly_credits=plan.monthly_credits,
            max_file_bytes=plan.max_file_bytes,
            max_pages=plan.max_pages,
            max_ai_requests_per_day=plan.max_ai_requests_per_day,
            features=plan.features or {},
        )
        for plan in plans
    ]


@router.get("/usage")
def usage(user: User = Depends(require_user), db: Session = Depends(get_db)) -> dict:
    account = CreditService(db).ensure_account(user)
    costs = {row.operation: row.credits for row in db.scalars(select(OperationCost))}
    return {
        "plan": user.plan_slug,
        "balance": account.balance,
        "reserved": account.reserved,
        "available": account.balance - account.reserved,
        "period_allowance": account.period_allowance,
        "period_used": account.period_used,
        "operation_costs": costs,
        "policy": {
            "refund_failed_jobs": True,
            "allow_negative_credits": False,
            "integer_credits_only": True,
        },
    }


@router.get("/ledger", response_model=list[LedgerOut])
def ledger(user: User = Depends(require_user), db: Session = Depends(get_db)) -> list[LedgerOut]:
    rows = db.scalars(
        select(CreditLedger).where(CreditLedger.user_id == user.id).order_by(CreditLedger.created_at.desc()).limit(100)
    )
    return [
        LedgerOut(
            id=row.id,
            amount=row.amount,
            entry_type=row.entry_type,
            description=row.description,
            job_id=row.job_id,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/checkout")
def checkout(request: Request, user: User = Depends(require_user)) -> dict:
    plan = request.query_params.get("plan") or "free"
    return {
        "status": "not_activated",
        "message": "All accounts use the Free plan. Paid checkout is disabled.",
        "plan": plan,
        "providers": ["stripe", "midtrans"],
        "next_step": "Configure STRIPE_* or MIDTRANS_* secrets, then enable sandbox webhooks.",
    }
