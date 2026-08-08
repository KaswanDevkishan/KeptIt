from datetime import UTC, datetime, timedelta
from typing import cast

from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.sessions import hash_session_token
from app.core.config import get_settings
from app.models.user import User, UserSession

PASSWORD = "correct horse battery staple"


def register(
    client: TestClient, email: str = "person@example.com", password: str = PASSWORD
) -> Response:
    return cast(
        Response,
        client.post("/api/v1/auth/register", json={"email": email, "password": password}),
    )


def test_successful_registration_sets_session_and_returns_public_user(
    client: TestClient, db_session: Session
) -> None:
    response = register(client)

    assert response.status_code == 201
    assert response.json()["email"] == "person@example.com"
    assert "password_hash" not in response.json()
    assert "token_hash" not in response.json()
    assert response.cookies.get("keptit_session")
    assert "HttpOnly" in response.headers["set-cookie"]
    assert db_session.scalar(select(User)) is not None


def test_registration_normalizes_email(client: TestClient, db_session: Session) -> None:
    response = register(client, "  PERSON@Example.COM ")

    assert response.status_code == 201
    assert response.json()["email"] == "person@example.com"
    assert db_session.scalar(select(User.email)) == "person@example.com"


def test_duplicate_registration_is_rejected(client: TestClient) -> None:
    assert register(client).status_code == 201
    response = register(client, "PERSON@example.com")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_registered"


def test_invalid_email_is_rejected(client: TestClient) -> None:
    response = register(client, "not-an-email")
    assert response.status_code == 422


def test_short_password_is_rejected(client: TestClient) -> None:
    response = register(client, password="too-short")
    assert response.status_code == 422


def test_successful_login(client: TestClient) -> None:
    register(client)
    client.cookies.clear()

    response = client.post(
        "/api/v1/auth/login", json={"email": " PERSON@example.com ", "password": PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["email"] == "person@example.com"
    assert response.cookies.get("keptit_session")


def test_bad_password_and_unknown_email_have_same_failure(client: TestClient) -> None:
    register(client)
    bad_password = client.post(
        "/api/v1/auth/login", json={"email": "person@example.com", "password": "wrong"}
    )
    unknown = client.post(
        "/api/v1/auth/login", json={"email": "unknown@example.com", "password": "wrong"}
    )

    assert bad_password.status_code == unknown.status_code == 401
    assert bad_password.json() == unknown.json()


def test_current_user_requires_and_accepts_valid_session(client: TestClient) -> None:
    assert client.get("/api/v1/users/me").status_code == 401
    register(client)

    response = client.get("/api/v1/users/me")

    assert response.status_code == 200
    assert response.json()["email"] == "person@example.com"


def test_logout_revokes_session_and_is_idempotent(client: TestClient, db_session: Session) -> None:
    register(client)
    raw_token = client.cookies.get("keptit_session")
    assert raw_token is not None

    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    record = db_session.scalar(select(UserSession))
    assert record is not None and record.revoked_at is not None
    client.cookies.set("keptit_session", raw_token)
    assert client.get("/api/v1/users/me").status_code == 401
    client.cookies.clear()
    assert client.post("/api/v1/auth/logout").status_code == 204


def test_expired_session_is_rejected(client: TestClient, db_session: Session) -> None:
    register(client)
    record = db_session.scalar(select(UserSession))
    assert record is not None
    record.created_at = datetime.now(UTC) - timedelta(hours=2)
    record.expires_at = datetime.now(UTC) - timedelta(hours=1)
    db_session.commit()

    assert client.get("/api/v1/users/me").status_code == 401


def test_secrets_are_hashed_at_rest(client: TestClient, db_session: Session) -> None:
    register(client)
    raw_token = client.cookies.get("keptit_session")
    user = db_session.scalar(select(User))
    session = db_session.scalar(select(UserSession))

    assert raw_token is not None and user is not None and session is not None
    assert user.password_hash != PASSWORD
    assert PASSWORD not in user.password_hash
    assert session.token_hash == hash_session_token(raw_token)
    assert raw_token.encode() != session.token_hash


def test_cross_origin_state_change_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "person@example.com", "password": PASSWORD},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_rejected"


def test_cookie_security_configuration_is_applied(client: TestClient) -> None:
    response = register(client)
    cookie = response.headers["set-cookie"]
    settings = get_settings()

    assert f"Max-Age={settings.session_duration_seconds}" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    assert "Domain=" not in cookie


def test_production_cookie_has_secure_cross_site_attributes(client: TestClient) -> None:
    settings = get_settings()
    original_secure = settings.session_cookie_secure
    original_samesite = settings.session_cookie_samesite
    try:
        settings.session_cookie_secure = True
        settings.session_cookie_samesite = "none"
        cookie = register(client).headers["set-cookie"]
    finally:
        settings.session_cookie_secure = original_secure
        settings.session_cookie_samesite = original_samesite

    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=none" in cookie
    assert "Path=/" in cookie
    assert f"Max-Age={settings.session_duration_seconds}" in cookie
    assert "Domain=" not in cookie


def test_cors_allows_configured_credentials_and_rejects_other_origins(client: TestClient) -> None:
    allowed = client.options(
        "/api/v1/users/me",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    rejected = client.options(
        "/api/v1/users/me",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert allowed.headers["access-control-allow-credentials"] == "true"
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers
