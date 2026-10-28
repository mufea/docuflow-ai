from __future__ import annotations

import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient

from tests.conftest import register_and_login


def test_stripe_webhook_grants_plan(client: TestClient) -> None:
    register_and_login(client, "payer@example.com")
    payload = {
        "id": "evt_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer_email": "payer@example.com",
                "status": "complete",
                "metadata": {"plan_slug": "pro", "credits": 500},
                "subscription": "sub_1",
            }
        },
    }
    body = json.dumps(payload).encode()
    timestamp = str(int(time.time()))
    signed = f"{timestamp}.".encode() + body
    signature = hmac.new(b"whsec_test", signed, hashlib.sha256).hexdigest()
    header = f"t={timestamp},v1={signature}"
    response = client.post("/v1/webhooks/stripe", content=body, headers={"stripe-signature": header})
    assert response.status_code == 200, response.text
    me = client.get("/v1/auth/me").json()
    assert me["plan_slug"] == "pro"
    duplicate = client.post("/v1/webhooks/stripe", content=body, headers={"stripe-signature": header})
    assert duplicate.json()["status"] == "duplicate"


def test_stripe_webhook_rejects_bad_signature(client: TestClient) -> None:
    body = b'{"id":"evt_bad","type":"checkout.session.completed","data":{"object":{}}}'
    response = client.post("/v1/webhooks/stripe", content=body, headers={"stripe-signature": "t=1,v1=deadbeef"})
    assert response.status_code in {401, 403}


def test_midtrans_webhook(client: TestClient) -> None:
    register_and_login(client, "id-user@example.com")
    payload = {
        "transaction_id": "trx-1",
        "order_id": "order-1",
        "status_code": "200",
        "gross_amount": "150000.00",
        "transaction_status": "settlement",
        "email": "id-user@example.com",
        "metadata": {"plan_slug": "pro", "credits": 500, "email": "id-user@example.com"},
    }
    signature = hashlib.sha512(
        f"{payload['order_id']}{payload['status_code']}{payload['gross_amount']}midtrans-test".encode()
    ).hexdigest()
    payload["signature_key"] = signature
    body = json.dumps(payload).encode()
    response = client.post("/v1/webhooks/midtrans", content=body)
    assert response.status_code == 200, response.text
    assert client.get("/v1/auth/me").json()["plan_slug"] == "pro"


def test_browser_redirect_does_not_grant_entitlements(client: TestClient) -> None:
    register_and_login(client)
    checkout = client.post("/v1/billing/checkout?plan=business")
    assert checkout.json()["status"] == "not_activated"
    assert client.get("/v1/auth/me").json()["plan_slug"] == "free"
