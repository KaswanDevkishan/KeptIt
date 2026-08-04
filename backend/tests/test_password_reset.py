from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.password_resets import hash_reset_token
from app.email.delivery import DevelopmentFileEmailSender, get_email_sender
from app.main import app
from app.models.user import PasswordResetToken, User, UserSession

PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "a new correct horse battery staple"
GENERIC_MESSAGE = "If an account exists for that email, password reset instructions have been sent."


class MemoryEmailSender:
    def __init__(self) -> None:
        self.deliveries: list[tuple[str, str]] = []

    def send_password_reset(self, email: str, raw_token: str) -> None:
        self.deliveries.append((email, raw_token))


def register(client: TestClient) -> Response:
    return cast(
        Response,
        client.post(
            "/api/v1/auth/register",
            json={"email": "person@example.com", "password": PASSWORD},
        ),
    )


@pytest.fixture
def email_sender() -> Generator[MemoryEmailSender, None, None]:
    sender = MemoryEmailSender()
    app.dependency_overrides[get_email_sender] = lambda: sender
    yield sender
    app.dependency_overrides.pop(get_email_sender, None)


def request_reset(client: TestClient, email: str) -> Response:
    return cast(
        Response,
        client.post("/api/v1/auth/password-reset/request", json={"email": email}),
    )


def confirm_reset(client: TestClient, token: str, password: str = NEW_PASSWORD) -> Response:
    return cast(
        Response,
        client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": password},
        ),
    )


def test_existing_and_unknown_accounts_receive_identical_generic_response(
    client: TestClient, email_sender: MemoryEmailSender
) -> None:
    register(client)
    existing = request_reset(client, " PERSON@example.com ")
    unknown = request_reset(client, "unknown@example.com")

    assert existing.status_code == unknown.status_code == 200
    assert existing.json() == unknown.json() == {"message": GENERIC_MESSAGE}
    assert [delivery[0] for delivery in email_sender.deliveries] == ["person@example.com"]


def test_raw_token_is_not_stored_and_sha256_hash_is_stored(
    client: TestClient, db_session: Session, email_sender: MemoryEmailSender
) -> None:
    register(client)
    request_reset(client, "person@example.com")
    raw_token = email_sender.deliveries[0][1]
    record = db_session.scalar(select(PasswordResetToken))

    assert record is not None
    assert record.token_hash == hash_reset_token(raw_token)
    assert raw_token.encode() != record.token_hash


def test_new_request_supersedes_previous_unused_token(
    client: TestClient, db_session: Session, email_sender: MemoryEmailSender
) -> None:
    register(client)
    request_reset(client, "person@example.com")
    first_token = email_sender.deliveries[-1][1]
    request_reset(client, "person@example.com")
    second_token = email_sender.deliveries[-1][1]
    records = list(
        db_session.scalars(select(PasswordResetToken).order_by(PasswordResetToken.created_at))
    )

    assert len(records) == 2
    assert records[0].used_at is not None
    assert records[1].used_at is None
    assert confirm_reset(client, first_token).status_code == 400
    assert confirm_reset(client, second_token).status_code == 200


def test_successful_reset_changes_password_and_revokes_all_sessions(
    client: TestClient, db_session: Session, email_sender: MemoryEmailSender
) -> None:
    register(client)
    client.cookies.clear()
    client.post("/api/v1/auth/login", json={"email": "person@example.com", "password": PASSWORD})
    request_reset(client, "person@example.com")
    token = email_sender.deliveries[-1][1]

    response = confirm_reset(client, token)

    assert response.status_code == 200
    assert client.get("/api/v1/users/me").status_code == 401
    sessions = list(db_session.scalars(select(UserSession)))
    assert len(sessions) == 2
    assert all(session.revoked_at is not None for session in sessions)
    client.cookies.clear()
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "person@example.com", "password": PASSWORD}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "person@example.com", "password": NEW_PASSWORD}
        ).status_code
        == 200
    )


def test_expired_used_and_invalid_tokens_share_safe_failure(
    client: TestClient, db_session: Session, email_sender: MemoryEmailSender
) -> None:
    register(client)
    request_reset(client, "person@example.com")
    expired_token = email_sender.deliveries[-1][1]
    expired = db_session.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_reset_token(expired_token)
        )
    )
    assert expired is not None
    expired.created_at = datetime.now(UTC) - timedelta(hours=1)
    expired.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    expired_response = confirm_reset(client, expired_token)
    invalid_response = confirm_reset(client, "not-a-real-token")
    request_reset(client, "person@example.com")
    used_token = email_sender.deliveries[-1][1]
    assert confirm_reset(client, used_token).status_code == 200
    used_response = confirm_reset(client, used_token)

    assert (
        expired_response.status_code
        == invalid_response.status_code
        == used_response.status_code
        == 400
    )
    assert expired_response.json() == invalid_response.json() == used_response.json()
    assert expired_response.json()["error"]["code"] == "invalid_password_reset"


def test_password_validation_is_enforced_before_token_use(
    client: TestClient, db_session: Session, email_sender: MemoryEmailSender
) -> None:
    register(client)
    request_reset(client, "person@example.com")
    token = email_sender.deliveries[-1][1]

    assert confirm_reset(client, token, "short").status_code == 422
    record = db_session.scalar(select(PasswordResetToken))
    assert record is not None and record.used_at is None


def test_inactive_user_receives_generic_response_without_delivery(
    client: TestClient, db_session: Session, email_sender: MemoryEmailSender
) -> None:
    register(client)
    user = db_session.scalar(select(User))
    assert user is not None
    user.is_active = False
    db_session.commit()

    response = request_reset(client, "person@example.com")

    assert response.status_code == 200
    assert response.json() == {"message": GENERIC_MESSAGE}
    assert email_sender.deliveries == []
    assert db_session.scalar(select(PasswordResetToken)) is None


def test_development_file_outbox_captures_fragment_reset_url(tmp_path: Path) -> None:
    outbox = tmp_path / "outbox.jsonl"
    sender = DevelopmentFileEmailSender("http://localhost:5173/reset-password", outbox)

    sender.send_password_reset("person@example.com", "raw reset token")

    content = outbox.read_text(encoding="utf-8")
    assert '"email": "person@example.com"' in content
    url_text = content.split('"reset_url": "', 1)[1].split('"', 1)[0]
    parsed = urlparse(url_text)
    assert parsed.query == ""
    assert parse_qs(parsed.fragment)["token"] == ["raw reset token"]
    assert outbox.stat().st_mode & 0o777 == 0o600
