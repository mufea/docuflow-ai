from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import register_and_login


def test_register_login_me_logout(client: TestClient) -> None:
    created = client.post(
        "/v1/auth/register",
        json={"email": "ada@example.com", "password": "super-secret-1", "name": "Ada"},
    )
    assert created.status_code == 200
    assert created.json()["credits_available"] == 50
    login = client.post("/v1/auth/login", json={"email": "ada@example.com", "password": "super-secret-1"})
    assert login.status_code == 200
    me = client.get("/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "ada@example.com"
    logout = client.post("/v1/auth/logout")
    assert logout.status_code == 200
    denied = client.get("/v1/auth/me")
    assert denied.status_code == 401


def test_invalid_login_is_generic(client: TestClient) -> None:
    client.post("/v1/auth/register", json={"email": "ada@example.com", "password": "super-secret-1", "name": "Ada"})
    response = client.post("/v1/auth/login", json={"email": "ada@example.com", "password": "wrong-password"})
    assert response.status_code == 401
    assert "password" not in response.json()["message"].lower() or "invalid" in response.json()["message"].lower()


def test_csrf_required_for_profile_update(client: TestClient) -> None:
    register_and_login(client)
    missing = client.patch("/v1/auth/me", json={"name": "Hacker"})
    assert missing.status_code == 403
    csrf = client.cookies.get("df_csrf")
    ok = client.patch(
        "/v1/auth/me", json={"name": "Grace"}, headers={"X-CSRF-Token": csrf, "Origin": "http://testserver"}
    )
    assert ok.status_code == 200
    assert ok.json()["name"] == "Grace"
