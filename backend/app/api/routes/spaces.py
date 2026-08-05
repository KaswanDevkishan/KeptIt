import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import func, select

from app.api.dependencies import CurrentUser, DbSession, TrustedOrigin
from app.models.space import Space, SpaceMembership
from app.schemas.space import (
    PublicSpace,
    PublicSpaceMembership,
    SpaceCreate,
    SpaceDiscoveryList,
    SpaceList,
    SpaceUpdate,
)
from app.services import spaces

router = APIRouter(prefix="/spaces", tags=["spaces"])


def public_space(db: DbSession, space: Space) -> PublicSpace:
    count = (
        db.scalar(
            select(func.count(SpaceMembership.id)).where(
                SpaceMembership.user_id == space.user_id, SpaceMembership.space_id == space.id
            )
        )
        or 0
    )
    return PublicSpace.model_validate(space).model_copy(update={"discovery_count": count})


@router.post("", response_model=PublicSpace, status_code=status.HTTP_201_CREATED)
def create_space(
    payload: SpaceCreate,
    response: Response,
    db: DbSession,
    user: CurrentUser,
    _origin: TrustedOrigin,
) -> PublicSpace:
    space = spaces.create_space(db, user.id, payload)
    response.headers["Location"] = f"/api/v1/spaces/{space.id}"
    return public_space(db, space)


@router.get("", response_model=SpaceList)
def list_spaces(
    db: DbSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
    sort: Literal["updated_desc", "name_asc"] = "updated_desc",
) -> SpaceList:
    rows, next_cursor = spaces.list_spaces(db, user.id, limit=limit, cursor=cursor, sort=sort)
    return SpaceList(
        items=[
            PublicSpace.model_validate(space).model_copy(update={"discovery_count": count})
            for space, count in rows
        ],
        next_cursor=next_cursor,
    )


@router.get("/{space_id}", response_model=PublicSpace)
def get_space(space_id: uuid.UUID, db: DbSession, user: CurrentUser) -> PublicSpace:
    return public_space(db, spaces.get_owned(db, user.id, space_id))


@router.patch("/{space_id}", response_model=PublicSpace)
def update_space(
    space_id: uuid.UUID,
    payload: SpaceUpdate,
    db: DbSession,
    user: CurrentUser,
    _origin: TrustedOrigin,
) -> PublicSpace:
    space = spaces.rename_space(db, spaces.get_owned(db, user.id, space_id), payload)
    return public_space(db, space)


@router.delete("/{space_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_space(
    space_id: uuid.UUID, db: DbSession, user: CurrentUser, _origin: TrustedOrigin
) -> None:
    spaces.delete_space(db, spaces.get_owned(db, user.id, space_id))


@router.get("/{space_id}/discoveries", response_model=SpaceDiscoveryList)
def list_space_discoveries(
    space_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
    archive: Literal["active", "archived", "all"] = "active",
) -> SpaceDiscoveryList:
    items, next_cursor = spaces.list_space_discoveries(
        db, user.id, space_id, limit=limit, cursor=cursor, archive=archive
    )
    return SpaceDiscoveryList(items=items, next_cursor=next_cursor)


@router.put("/{space_id}/discoveries/{discovery_id}", response_model=PublicSpaceMembership)
@router.post(
    "/{space_id}/discoveries/{discovery_id}",
    response_model=PublicSpaceMembership,
    include_in_schema=False,
)
def add_discovery_to_space(
    space_id: uuid.UUID,
    discovery_id: uuid.UUID,
    response: Response,
    db: DbSession,
    user: CurrentUser,
    _origin: TrustedOrigin,
) -> SpaceMembership:
    membership, created = spaces.add_discovery_to_space(db, user.id, space_id, discovery_id)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return membership


@router.delete("/{space_id}/discoveries/{discovery_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_discovery_from_space(
    space_id: uuid.UUID,
    discovery_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    _origin: TrustedOrigin,
) -> None:
    spaces.remove_discovery_from_space(db, user.id, space_id, discovery_id)
