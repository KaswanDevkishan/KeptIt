import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.user import PasswordResetToken, UserSession


@dataclass(frozen=True)
class CreatedPasswordReset:
    record: PasswordResetToken
    raw_token: str


def hash_reset_token(raw_token: str) -> bytes:
    return hashlib.sha256(raw_token.encode("utf-8")).digest()


def create_password_reset(
    db: Session, user_id: uuid.UUID, lifetime_seconds: int
) -> CreatedPasswordReset:
    raw_token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    record = PasswordResetToken(
        user_id=user_id,
        token_hash=hash_reset_token(raw_token),
        created_at=now,
        expires_at=now + timedelta(seconds=lifetime_seconds),
    )
    db.add(record)
    return CreatedPasswordReset(record=record, raw_token=raw_token)


def find_valid_password_reset(db: Session, raw_token: str) -> PasswordResetToken | None:
    presented_hash = hash_reset_token(raw_token)
    record = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == presented_hash)
        .with_for_update()
    )
    if record is None or not hmac.compare_digest(record.token_hash, presented_hash):
        return None
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if record.used_at is not None or expires_at <= datetime.now(UTC):
        return None
    return record


def revoke_all_user_sessions(db: Session, user_id: uuid.UUID, revoked_at: datetime) -> None:
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=revoked_at)
    )
