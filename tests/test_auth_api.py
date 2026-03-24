from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import AuthSettings
from app.core.container import build_container
from app.main import create_app


def test_auth_login_flow_requires_session(studio_settings) -> None:
    studio_settings.auth = AuthSettings(
        enabled=True,
        username="tester",
        password="secret123",
        session_secret="test-session-secret",
    )

    container = build_container(studio_settings)
    try:
        with TestClient(create_app(container)) as client:
            session_response = client.get("/auth/session")
            assert session_response.status_code == 200
            assert session_response.json()["data"] == {
                "enabled": True,
                "authenticated": False,
                "username": None,
            }
    finally:
        container.shutdown()


def test_auth_login_and_logout(studio_settings) -> None:
    studio_settings.auth = AuthSettings(
        enabled=True,
        username="tester",
        password="secret123",
        session_secret="test-session-secret",
    )

    container = build_container(studio_settings)
    try:
        with TestClient(create_app(container)) as client:
            unauthorized = client.get("/projects")
            assert unauthorized.status_code == 401

            bad_login = client.post("/auth/login", json={"username": "tester", "password": "wrong"})
            assert bad_login.status_code == 401

            login = client.post(
                "/auth/login",
                json={"username": "tester", "password": "secret123"},
            )
            assert login.status_code == 200
            assert login.json()["data"]["authenticated"] is True
            assert login.json()["data"]["username"] == "tester"

            authorized = client.get("/projects")
            assert authorized.status_code == 200

            logout = client.post("/auth/logout")
            assert logout.status_code == 200
            assert logout.json()["data"]["authenticated"] is False

            unauthorized_again = client.get("/projects")
            assert unauthorized_again.status_code == 401
    finally:
        container.shutdown()
