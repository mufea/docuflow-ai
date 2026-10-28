from __future__ import annotations

import hashlib
import hmac
import json
import time

from docuflow.config import Settings
from docuflow.exceptions import AuthorizationError, ValidationError
from docuflow.payments.base import WebhookResult

PLAN_BY_PRICE_HINT = {
    "pro": "pro",
    "business": "business",
}


class StripeAdapter:
    name = "stripe"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def verify_and_parse(self, payload: bytes, headers: dict[str, str]) -> WebhookResult:
        secret = self.settings.reveal_secret(self.settings.stripe_webhook_secret)
        if not secret:
            raise ValidationError("Stripe webhook secret is not configured.")
        signature = headers.get("stripe-signature") or headers.get("Stripe-Signature")
        if not signature:
            raise AuthorizationError("Missing Stripe signature.")
        _verify_stripe_signature(payload, signature, secret)
        body = json.loads(payload.decode("utf-8"))
        event_id = str(body.get("id") or "")
        event_type = str(body.get("type") or "")
        data = body.get("data", {}).get("object", {})
        email = data.get("customer_email") or data.get("receipt_email")
        if not email and isinstance(data.get("customer_details"), dict):
            email = data["customer_details"].get("email")
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        plan = metadata.get("plan_slug") or _plan_from_price(data, self.settings)
        credits = int(metadata.get("credits") or 0)
        status = data.get("status")
        subscription_id = data.get("subscription") if event_type.startswith("checkout") else data.get("id")
        if event_type in {"checkout.session.completed", "invoice.paid", "customer.subscription.updated"}:
            credits = credits or _credits_for_plan(plan)
            status = status or "active"
        return WebhookResult(
            provider=self.name,
            event_id=event_id,
            event_type=event_type,
            user_email=email,
            plan_slug=plan,
            credits=credits,
            subscription_status=status,
            provider_subscription_id=str(subscription_id) if subscription_id else None,
            raw_type=event_type,
        )


def _credits_for_plan(plan: str | None) -> int:
    return {"pro": 500, "business": 2000}.get(plan or "", 0)


def _plan_from_price(data: dict[str, object], settings: Settings) -> str | None:
    price = None
    items = data.get("items")
    if isinstance(items, dict) and isinstance(items.get("data"), list) and items["data"]:
        price = items["data"][0].get("price", {}).get("id")
    if data.get("display_items"):
        price = None
    if price == settings.stripe_price_pro:
        return "pro"
    if price == settings.stripe_price_business:
        return "business"
    return None


def _verify_stripe_signature(payload: bytes, header: str, secret: str, *, tolerance: int = 300) -> None:
    items = dict(part.split("=", 1) for part in header.split(",") if "=" in part)
    timestamp = items.get("t")
    signature = items.get("v1")
    if not timestamp or not signature:
        raise AuthorizationError("Malformed Stripe signature.")
    if abs(time.time() - int(timestamp)) > tolerance:
        raise AuthorizationError("Stripe signature timestamp is outside the allowed window.")
    signed = f"{timestamp}.".encode() + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise AuthorizationError("Invalid Stripe signature.")
