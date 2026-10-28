from __future__ import annotations

import hashlib

from fastapi import APIRouter, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from docuflow.billing.ledger import CreditService
from docuflow.exceptions import NotFoundError, ValidationError
from docuflow.models import PaymentEvent, Subscription, User
from docuflow.payments.midtrans_adapter import MidtransAdapter
from docuflow.payments.stripe_adapter import StripeAdapter

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


@router.post("/stripe")
async def stripe_webhook(request: Request) -> dict[str, str]:
    payload = await request.body()
    adapter = StripeAdapter(request.app.state.ctx.settings)
    result = adapter.verify_and_parse(payload, dict(request.headers))
    return _apply_payment(request.app.state.ctx.session_factory(), payload, result)


@router.post("/midtrans")
async def midtrans_webhook(request: Request) -> dict[str, str]:
    payload = await request.body()
    adapter = MidtransAdapter(request.app.state.ctx.settings)
    result = adapter.verify_and_parse(payload, dict(request.headers))
    return _apply_payment(request.app.state.ctx.session_factory(), payload, result)


def _apply_payment(session: Session, payload: bytes, result) -> dict[str, str]:
    try:
        existing = session.scalar(
            select(PaymentEvent).where(
                PaymentEvent.provider == result.provider,
                PaymentEvent.provider_event_id == result.event_id,
            )
        )
        if existing:
            return {"status": "duplicate"}
        if not result.user_email:
            raise ValidationError("Webhook did not include a customer email.")
        user = session.scalar(select(User).where(User.email == result.user_email.lower()))
        if user is None:
            raise NotFoundError("No account matches this payment.")
        session.add(
            PaymentEvent(
                provider=result.provider,
                provider_event_id=result.event_id,
                event_type=result.event_type,
                payload_hash=hashlib.sha256(payload).hexdigest(),
            )
        )
        if result.plan_slug and result.subscription_status in {
            "active",
            "paid",
            "settlement",
            "capture",
            "complete",
            "completed",
        }:
            user.plan_slug = result.plan_slug
            session.add(
                Subscription(
                    user_id=user.id,
                    plan_slug=result.plan_slug,
                    status="active",
                    provider=result.provider,
                    provider_subscription_id=result.provider_subscription_id,
                )
            )
            if result.credits > 0:
                CreditService(session).grant(
                    user,
                    result.credits,
                    reason=f"{result.provider} {result.event_type}",
                    idempotency_key=f"pay:{result.provider}:{result.event_id}",
                    payment_id=result.event_id,
                )
        session.commit()
        return {"status": "ok"}
    finally:
        session.close()
