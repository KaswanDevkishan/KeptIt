from fastapi import APIRouter

from app.api.dependencies import CurrentUser
from app.models.user import User
from app.schemas.auth import PublicUser

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=PublicUser)
def current_user(user: CurrentUser) -> User:
    return user
