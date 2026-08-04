import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import UserSession


@dataclass(frozen=True)
class CreatedSession:
    record: UserSession
    raw_token: str


def hash_session_token(raw_token: str) -> bytes:
    return hashlib.sha256(raw_token.encode("utf-8")).digest()


def create_session(db: Session, user_id: uuid.UUID, duration_seconds: int) -> CreatedSession:
    raw_token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    record = UserSession(
        user_id=user_id,
        token_hash=hash_session_token(raw_token),
        created_at=now,
        expires_at=now + timedelta(seconds=duration_seconds),
    )
    db.add(record)
    return CreatedSession(record=record, raw_token=raw_token)


def find_valid_session(db: Session, raw_token: str) -> UserSession | None:
    presented_hash = hash_session_token(raw_token)
    record = db.scalar(select(UserSession).where(UserSession.token_hash == presented_hash))
    if record is None or not hmac.compare_digest(record.token_hash, presented_hash):
        return None
    now = datetime.now(UTC)
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if record.revoked_at is not None or expires_at <= now:
        return None
    return record


def revoke_session(record: UserSession) -> None:
    if record.revoked_at is None:
        record.revoked_at = datetime.now(UTC)
