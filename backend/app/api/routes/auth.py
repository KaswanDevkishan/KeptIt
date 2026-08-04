from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import AppSettings, DbSession, TrustedOrigin
from app.auth.passwords import hash_password, perform_dummy_verification, verify_password
from app.auth.sessions import create_session, find_valid_session, revoke_session
from app.models.user import User
from app.schemas.auth import CredentialsRequest, LoginRequest, PublicUser

router = APIRouter(prefix="/auth", tags=["authentication"])

INVALID_CREDENTIALS = {
    "code": "invalid_credentials",
    "message": "Email or password is incorrect.",
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
