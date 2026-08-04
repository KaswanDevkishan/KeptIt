from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.sessions import find_valid_session
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.user import User, UserSession

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def unauthenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "unauthenticated", "message": "Authentication is required."},
    )


def get_current_session(
    request: Request,
    db: DbSession,
    settings: AppSettings,
) -> UserSession:
    token = request.cookies.get(settings.session_cookie_name)
    if token is None:
        raise unauthenticated()
    record = find_valid_session(db, token)
    if record is None or not record.user.is_active:
        raise unauthenticated()
    return record


CurrentSession = Annotated[UserSession, Depends(get_current_session)]


def get_current_user(session: CurrentSession) -> User:
    return session.user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_trusted_origin(request: Request, settings: AppSettings) -> None:
    origin = request.headers.get("origin")
    allowed = {str(item).rstrip("/") for item in settings.cors_origins}
    if origin is not None and origin.rstrip("/") not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "csrf_rejected", "message": "Request origin is not allowed."},
        )
    if settings.environment == "production" and origin is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "csrf_rejected", "message": "Request origin is required."},
        )


TrustedOrigin = Annotated[None, Depends(require_trusted_origin)]
