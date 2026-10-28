from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class WebhookResult:
    provider: str
    event_id: str
    event_type: str
    user_email: str | None
    plan_slug: str | None
    credits: int
    subscription_status: str | None
    provider_subscription_id: str | None
    raw_type: str


class PaymentProvider(Protocol):
    name: str

    def verify_and_parse(self, payload: bytes, headers: dict[str, str]) -> WebhookResult: ...
