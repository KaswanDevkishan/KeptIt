import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import func, select

from app.api.dependencies import CurrentUser, DbSession, TrustedOrigin
from app.models.tag import DiscoveryTag, Tag
from app.schemas.tag import (
    PublicTag,
    PublicTagMembership,
    TagCreate,
    TagDiscoveryList,
    TagList,
    TagUpdate,
)
from app.services import tags

router = APIRouter(prefix="/tags", tags=["tags"])


def public_tag(db: DbSession, tag: Tag) -> PublicTag:
    count = (
        db.scalar(
            select(func.count(DiscoveryTag.id)).where(
                DiscoveryTag.user_id == tag.user_id, DiscoveryTag.tag_id == tag.id
            )
        )
        or 0
    )
    return PublicTag.model_validate(tag).model_copy(update={"discovery_count": count})


@router.post("", response_model=PublicTag, status_code=status.HTTP_201_CREATED)
def create_tag(
    payload: TagCreate, response: Response, db: DbSession, user: CurrentUser, _origin: TrustedOrigin
) -> PublicTag:
    tag = tags.create_tag(db, user.id, payload)
    response.headers["Location"] = f"/api/v1/tags/{tag.id}"
    return public_tag(db, tag)


@router.get("", response_model=TagList)
def list_tags(
    db: DbSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
    q: Annotated[str | None, Query(min_length=1, max_length=50)] = None,
    sort: Literal["name_asc", "updated_desc"] = "name_asc",
) -> TagList:
    rows, next_cursor = tags.list_tags(db, user.id, limit=limit, cursor=cursor, q=q, sort=sort)
    return TagList(
        items=[
            PublicTag.model_validate(tag).model_copy(update={"discovery_count": count})
            for tag, count in rows
        ],
        next_cursor=next_cursor,
    )


@router.get("/{tag_id}", response_model=PublicTag)
def get_tag(tag_id: uuid.UUID, db: DbSession, user: CurrentUser) -> PublicTag:
    return public_tag(db, tags.get_owned(db, user.id, tag_id))


@router.patch("/{tag_id}", response_model=PublicTag)
def update_tag(
    tag_id: uuid.UUID, payload: TagUpdate, db: DbSession, user: CurrentUser, _origin: TrustedOrigin
) -> PublicTag:
    return public_tag(db, tags.rename_tag(db, tags.get_owned(db, user.id, tag_id), payload))


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(tag_id: uuid.UUID, db: DbSession, user: CurrentUser, _origin: TrustedOrigin) -> None:
    tags.delete_tag(db, tags.get_owned(db, user.id, tag_id))


@router.put("/{tag_id}/discoveries/{discovery_id}", response_model=PublicTagMembership)
def attach(
    tag_id: uuid.UUID,
    discovery_id: uuid.UUID,
    response: Response,
    db: DbSession,
    user: CurrentUser,
    _origin: TrustedOrigin,
) -> DiscoveryTag:
    membership, created = tags.attach_tag_to_discovery(db, user.id, tag_id, discovery_id)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return membership


@router.delete("/{tag_id}/discoveries/{discovery_id}", status_code=status.HTTP_204_NO_CONTENT)
def detach(
    tag_id: uuid.UUID,
    discovery_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    _origin: TrustedOrigin,
) -> None:
    tags.detach_tag_from_discovery(db, user.id, tag_id, discovery_id)


@router.get("/{tag_id}/discoveries", response_model=TagDiscoveryList)
def list_discoveries(
    tag_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
    archive: Literal["active", "archived", "all"] = "active",
) -> TagDiscoveryList:
    items, next_cursor = tags.list_tag_discoveries(
        db, user.id, tag_id, limit=limit, cursor=cursor, archive=archive
    )
    return TagDiscoveryList(items=items, next_cursor=next_cursor)
