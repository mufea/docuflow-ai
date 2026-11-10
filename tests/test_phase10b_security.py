from __future__ import annotations

import threading

from starlette.requests import Request

from docuflow.exceptions import RateLimitError
from docuflow.security import rate_limit as rate_limit_module
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


def _assert_rate_limited(response) -> None:
    assert response.status_code == 429
    body = response.json()
    assert body["error"] == "rate_limited"
    assert body["message"] == "Too many requests. Try again shortly."


def test_reset_password_quota_is_per_client(client, monkeypatch) -> None:
    identities = ["10.0.0.1"] * 11 + ["10.0.0.2"]
    cursor = iter(identities)
    monkeypatch.setattr(
        "docuflow.api.routes.auth.rate_limit_client_id",
        lambda _request: next(cursor),
    )
    payload = {"token": "not-a-real-reset-token", "password": "super-secret-1"}
    responses = [client.post("/v1/auth/reset-password", json=payload) for _ in range(11)]
    assert [item.status_code for item in responses[:10]] == [401] * 10
    _assert_rate_limited(responses[10])
    other = client.post("/v1/auth/reset-password", json=payload)
    assert other.status_code == 401


def test_verify_email_quota_is_per_client(client, monkeypatch) -> None:
    identities = ["10.0.0.1"] * 11 + ["10.0.0.2"]
    cursor = iter(identities)
    monkeypatch.setattr(
        "docuflow.api.routes.auth.rate_limit_client_id",
        lambda _request: next(cursor),
    )
    payload = {"token": "not-a-real-verify-token"}
    responses = [client.post("/v1/auth/verify-email", json=payload) for _ in range(11)]
    assert [item.status_code for item in responses[:10]] == [401] * 10
    _assert_rate_limited(responses[10])
    other = client.post("/v1/auth/verify-email", json=payload)
    assert other.status_code == 401


def test_reset_and_verify_quotas_are_independent(client) -> None:
    reset_payload = {"token": "not-a-real-reset-token", "password": "super-secret-1"}
    verify_payload = {"token": "not-a-real-verify-token"}
    for _ in range(10):
        assert client.post("/v1/auth/reset-password", json=reset_payload).status_code == 401
    _assert_rate_limited(client.post("/v1/auth/reset-password", json=reset_payload))
    assert client.post("/v1/auth/verify-email", json=verify_payload).status_code == 401


def test_reset_password_xff_cannot_bypass_peer_limit(client) -> None:
    payload = {"token": "not-a-real-reset-token", "password": "super-secret-1"}
    statuses = []
    for index in range(11):
        response = client.post(
            "/v1/auth/reset-password",
            json=payload,
            headers={"X-Forwarded-For": f"198.51.100.{index}", "X-Real-IP": f"203.0.113.{index}"},
        )
        statuses.append(response.status_code)
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429
    _assert_rate_limited(client.post("/v1/auth/reset-password", json=payload))


def test_verify_email_xff_cannot_bypass_peer_limit(client) -> None:
    payload = {"token": "not-a-real-verify-token"}
    statuses = []
    for index in range(11):
        response = client.post(
            "/v1/auth/verify-email",
            json=payload,
            headers={"X-Forwarded-For": f"198.51.100.{index}", "X-Real-IP": f"203.0.113.{index}"},
        )
        statuses.append(response.status_code)
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429
    _assert_rate_limited(client.post("/v1/auth/verify-email", json=payload))


def test_expired_empty_bucket_is_evicted(monkeypatch) -> None:
    limiter = MemoryRateLimiter()
    clock = {"now": 1000.0}
    monkeypatch.setattr(rate_limit_module.time, "monotonic", lambda: clock["now"])
    limiter.hit("idle:1.1.1.1", limit=3, window_seconds=10)
    limiter.hit("active:2.2.2.2", limit=3, window_seconds=10)
    limiter.hit("active:2.2.2.2", limit=3, window_seconds=10)
    clock["now"] = 1005.0
    limiter.hit("active:2.2.2.2", limit=3, window_seconds=10)
    assert "idle:1.1.1.1" in limiter._hits
    assert len(limiter._hits["active:2.2.2.2"]) == 3
    clock["now"] = 1011.0
    limiter.hit("active:2.2.2.2", limit=3, window_seconds=10)
    assert "idle:1.1.1.1" not in limiter._hits
    assert "idle:1.1.1.1" not in limiter._windows
    assert len(limiter._hits["active:2.2.2.2"]) == 2


def test_evicted_key_can_be_reused(monkeypatch) -> None:
    limiter = MemoryRateLimiter()
    clock = {"now": 0.0}
    monkeypatch.setattr(rate_limit_module.time, "monotonic", lambda: clock["now"])
    for _ in range(2):
        limiter.hit("reuse:9.9.9.9", limit=2, window_seconds=10)
    try:
        limiter.hit("reuse:9.9.9.9", limit=2, window_seconds=10)
        raise AssertionError("active window must still limit")
    except RateLimitError:
        pass
    clock["now"] = 11.0
    limiter.hit("reuse:9.9.9.9", limit=2, window_seconds=10)
    limiter.hit("reuse:9.9.9.9", limit=2, window_seconds=10)
    try:
        limiter.hit("reuse:9.9.9.9", limit=2, window_seconds=10)
        raise AssertionError("reused key must honor the limit again")
    except RateLimitError:
        pass
    assert len(limiter._hits["reuse:9.9.9.9"]) == 2


def test_memory_limiter_concurrent_hits_respect_limit() -> None:
    limiter = MemoryRateLimiter()
    rejected = 0
    lock = threading.Lock()

    def worker() -> None:
        nonlocal rejected
        try:
            limiter.hit("concurrent:1.1.1.1", limit=40, window_seconds=60)
        except RateLimitError:
            with lock:
                rejected += 1

    threads = [threading.Thread(target=worker) for _ in range(80)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert rejected == 40
    assert len(limiter._hits["concurrent:1.1.1.1"]) == 40
