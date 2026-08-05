import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.dependencies import CurrentUser, DbSession, TrustedOrigin
from app.models.discovery import Discovery
from app.schemas.discovery import DiscoveryCreate, DiscoveryList, DiscoveryUpdate, PublicDiscovery
from app.services import discoveries
from app.services.urls import Platform

router = APIRouter(prefix="/discoveries", tags=["discoveries"])


@router.post("", response_model=PublicDiscovery, status_code=status.HTTP_201_CREATED)
def create_discovery(
    payload: DiscoveryCreate, db: DbSession, user: CurrentUser, _origin: TrustedOrigin
) -> Discovery:
    return discoveries.create(db, user.id, payload)


@router.get("", response_model=DiscoveryList)
def list_discoveries(
    db: DbSession,
    user: CurrentUser,
    q: Annotated[str | None, Query(max_length=300)] = None,
    platform: Platform | None = None,
    archived: bool = False,
    favourite: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> DiscoveryList:
    results, total = discoveries.list_owned(
        db,
        user.id,
        q=q,
        platform=platform,
        archived=archived,
        favourite=favourite,
        limit=limit,
        offset=offset,
    )
    return DiscoveryList(results=results, total=total, limit=limit, offset=offset)


@router.get("/{discovery_id}", response_model=PublicDiscovery)
def get_discovery(discovery_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Discovery:
    return discoveries.get_owned(db, user.id, discovery_id)


@router.patch("/{discovery_id}", response_model=PublicDiscovery)
def update_discovery(
    discovery_id: uuid.UUID,
    payload: DiscoveryUpdate,
    db: DbSession,
    user: CurrentUser,
    _origin: TrustedOrigin,
) -> Discovery:
    return discoveries.update(db, discoveries.get_owned(db, user.id, discovery_id), payload)


@router.post("/{discovery_id}/archive", response_model=PublicDiscovery)
def archive_discovery(
    discovery_id: uuid.UUID, db: DbSession, user: CurrentUser, _origin: TrustedOrigin
) -> Discovery:
    return discoveries.set_archived(db, discoveries.get_owned(db, user.id, discovery_id), True)


@router.post("/{discovery_id}/restore", response_model=PublicDiscovery)
def restore_discovery(
    discovery_id: uuid.UUID, db: DbSession, user: CurrentUser, _origin: TrustedOrigin
) -> Discovery:
    return discoveries.set_archived(db, discoveries.get_owned(db, user.id, discovery_id), False)


@router.delete("/{discovery_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_discovery(
    discovery_id: uuid.UUID, db: DbSession, user: CurrentUser, _origin: TrustedOrigin
) -> None:
    discoveries.delete(db, discoveries.get_owned(db, user.id, discovery_id))
