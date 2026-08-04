import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import AppSettings, DbSession, EmailSender, TrustedOrigin
from app.auth.password_resets import (
    create_password_reset,
    find_valid_password_reset,
    hash_reset_token,
    revoke_all_user_sessions,
)
from app.auth.passwords import hash_password, perform_dummy_verification, verify_password
from app.auth.sessions import create_session, find_valid_session, revoke_session
from app.models.user import User
from app.schemas.auth import (
    CredentialsRequest,
    LoginRequest,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PublicUser,
)

router = APIRouter(prefix="/auth", tags=["authentication"])

INVALID_CREDENTIALS = {
    "code": "invalid_credentials",
    "message": "Email or password is incorrect.",
}
PASSWORD_RESET_REQUESTED = (
    "If an account exists for that email, password reset instructions have been sent."
)
PASSWORD_RESET_INVALID = {
    "code": "invalid_password_reset",
    "message": "This password reset link is invalid or has expired.",
}


def set_session_cookie(response: Response, raw_token: str, settings: AppSettings) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=settings.session_duration_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,  # type: ignore[arg-type]
        path=settings.session_cookie_path,
    )


@router.post("/register", response_model=PublicUser, status_code=status.HTTP_201_CREATED)
def register(
    payload: CredentialsRequest,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    _origin: TrustedOrigin,
) -> User:
    user = User(email=str(payload.email), password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "email_registered", "message": "An account with this email exists."},
        ) from exc
    created = create_session(db, user.id, settings.session_duration_seconds)
    db.commit()
    db.refresh(user)
    set_session_cookie(response, created.raw_token, settings)
    return user


@router.post("/login", response_model=PublicUser)
def login(
    payload: LoginRequest,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    _origin: TrustedOrigin,
) -> User:
    user = db.scalar(select(User).where(User.email == str(payload.email)))
    if user is None:
        perform_dummy_verification(payload.password)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS)
    if not user.is_active or not verify_password(user.password_hash, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS)
    created = create_session(db, user.id, settings.session_duration_seconds)
    db.commit()
    set_session_cookie(response, created.raw_token, settings)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    _origin: TrustedOrigin,
) -> None:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if raw_token is not None:
        session = find_valid_session(db, raw_token)
        if session is not None:
            revoke_session(session)
            db.commit()
    response.delete_cookie(
        key=settings.session_cookie_name,
        path=settings.session_cookie_path,
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=settings.session_cookie_samesite,  # type: ignore[arg-type]
    )


@router.post("/password-reset/request", response_model=MessageResponse)
def request_password_reset(
    payload: PasswordResetRequest,
    db: DbSession,
    settings: AppSettings,
    email_sender: EmailSender,
    _origin: TrustedOrigin,
) -> MessageResponse:
    user = db.scalar(select(User).where(User.email == str(payload.email)))
    if user is None or not user.is_active:
        # Hashing a dummy reset token keeps the no-account path from being a trivial no-op.
        hash_reset_token(secrets.token_urlsafe(32))
        return MessageResponse(message=PASSWORD_RESET_REQUESTED)

    created = create_password_reset(db, user.id, settings.password_reset_token_lifetime_seconds)
    db.flush()
    email_sender.send_password_reset(user.email, created.raw_token)
    db.commit()
    return MessageResponse(message=PASSWORD_RESET_REQUESTED)


@router.post("/password-reset/confirm", response_model=MessageResponse)
def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    db: DbSession,
    _origin: TrustedOrigin,
) -> MessageResponse:
    record = find_valid_password_reset(db, payload.token)
    if record is None or not record.user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=PASSWORD_RESET_INVALID)

    now = datetime.now(UTC)
    record.user.password_hash = hash_password(payload.new_password)
    record.user.updated_at = now
    record.used_at = now
    revoke_all_user_sessions(db, record.user_id, now)
    db.commit()
    return MessageResponse(message="Your password has been reset. You can now sign in.")
