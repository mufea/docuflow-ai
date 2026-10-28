from __future__ import annotations

import hashlib
import hmac
import json

from docuflow.config import Settings
from docuflow.exceptions import AuthorizationError, ValidationError
from docuflow.payments.base import WebhookResult


class MidtransAdapter:
    name = "midtrans"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def verify_and_parse(self, payload: bytes, headers: dict[str, str]) -> WebhookResult:
        secret = self.settings.reveal_secret(self.settings.midtrans_server_key)
        if not secret:
            raise ValidationError("Midtrans server key is not configured.")
        body = json.loads(payload.decode("utf-8"))
        order_id = str(body.get("order_id") or "")
        status_code = str(body.get("status_code") or "")
        gross_amount = str(body.get("gross_amount") or "")
        signature = str(body.get("signature_key") or headers.get("x-signature") or "")
        expected = hashlib.sha512(f"{order_id}{status_code}{gross_amount}{secret}".encode()).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise AuthorizationError("Invalid Midtrans signature.")
        transaction_status = str(body.get("transaction_status") or "")
        metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        custom = body.get("custom_field1")
        plan = metadata.get("plan_slug") or custom
        email = metadata.get("email") or body.get("email")
        paid = transaction_status in {"capture", "settlement"}
        return WebhookResult(
            provider=self.name,
            event_id=str(body.get("transaction_id") or order_id),
            event_type=transaction_status,
            user_email=email,
            plan_slug=plan if paid else None,
            credits=int(metadata.get("credits") or (500 if plan == "pro" else 2000 if plan == "business" else 0)),
            subscription_status="active" if paid else transaction_status,
            provider_subscription_id=order_id,
            raw_type=transaction_status,
        )
