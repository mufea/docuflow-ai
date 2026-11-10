from __future__ import annotations

from starlette.requests import Request

from docuflow.exceptions import RateLimitError
from docuflow.security.client_ip import rate_limit_client_id
from docuflow.security.rate_limit import MemoryRateLimiter
from tests.conftest import register_and_login


def _request(*, host: str | None, headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/v1/auth/forgot-password",
        "raw_path": b"/v1/auth/forgot-password",
        "query_string": b"",
        "headers": headers or [],
        "client": (host, 12345) if host is not None else None,
        "server": ("testserver", 80),
    }
    return Request(scope)


def test_rate_limit_client_id_ignores_forwarded_headers() -> None:
    request = _request(
        host="10.0.0.8",
        headers=[
            (b"x-forwarded-for", b"203.0.113.9, 10.0.0.1"),
            (b"x-real-ip", b"198.51.100.2"),
            (b"forwarded", b"for=192.0.2.60"),
        ],
    )
    assert rate_limit_client_id(request) == "10.0.0.8"


def test_rate_limit_client_id_unknown_without_peer() -> None:
    request = _request(host=None)
    request.scope["client"] = None
    assert rate_limit_client_id(request) == "unknown"


def test_memory_limiter_isolates_clients() -> None:
    limiter = MemoryRateLimiter()
    for _ in range(8):
        limiter.hit("forgot:1.1.1.1", limit=8, window_seconds=60)
    try:
        limiter.hit("forgot:1.1.1.1", limit=8, window_seconds=60)
        raise AssertionError("same client must be limited")
    except RateLimitError:
        pass
    limiter.hit("forgot:2.2.2.2", limit=8, window_seconds=60)


def test_forgot_password_does_not_reveal_account(client) -> None:
    register_and_login(client, "known-reset@example.com")
    known = client.post("/v1/auth/forgot-password", json={"email": "known-reset@example.com"})
    unknown = client.post("/v1/auth/forgot-password", json={"email": "missing-reset@example.com"})
    assert known.status_code == 200
    assert unknown.status_code == 200
    assert known.json() == unknown.json() == {"ok": True}


def test_forgot_password_invalid_email_is_validation_error(client) -> None:
    response = client.post("/v1/auth/forgot-password", json={"email": "not-an-email"})
    assert response.status_code == 422


def test_forgot_password_quota_is_per_client(client, monkeypatch) -> None:
    identities = ["10.0.0.1"] * 9 + ["10.0.0.2"]
    cursor = iter(identities)
    monkeypatch.setattr(
        "docuflow.api.routes.auth.rate_limit_client_id",
        lambda _request: next(cursor),
    )
    payload = {"email": "anyone@example.com"}
    statuses = [client.post("/v1/auth/forgot-password", json=payload).status_code for _ in range(9)]
    assert statuses[:8] == [200] * 8
    assert statuses[8] == 429
    other = client.post("/v1/auth/forgot-password", json=payload)
    assert other.status_code == 200


def test_forgot_password_xff_cannot_bypass_peer_limit(client) -> None:
    payload = {"email": "xff@example.com"}
    statuses = []
    for index in range(9):
        response = client.post(
            "/v1/auth/forgot-password",
            json=payload,
            headers={"X-Forwarded-For": f"198.51.100.{index}", "X-Real-IP": f"203.0.113.{index}"},
        )
        statuses.append(response.status_code)
    assert statuses[:8] == [200] * 8
    assert statuses[8] == 429
    assert statuses[8] == client.post("/v1/auth/forgot-password", json=payload).status_code


def test_login_limit_is_independent_of_forgot(client) -> None:
    for _ in range(8):
        assert client.post("/v1/auth/forgot-password", json={"email": "limit@example.com"}).status_code == 200
    assert client.post("/v1/auth/forgot-password", json={"email": "limit@example.com"}).status_code == 429
    created = client.post(
        "/v1/auth/register",
        json={"email": "limit-login@example.com", "password": "super-secret-1", "name": "Limit"},
    )
    assert created.status_code == 200, created.text
    login = client.post(
        "/v1/auth/login",
        json={"email": "limit-login@example.com", "password": "super-secret-1"},
    )
    assert login.status_code == 200
