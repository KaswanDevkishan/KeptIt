import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.metadata.service import ensure_record
from app.models.discovery import Discovery
from app.schemas.discovery import DiscoveryCreate, DiscoveryUpdate
from app.services.urls import InvalidUrlError, Platform, normalize_url


def not_found() -> HTTPException:
    return HTTPException(
        status_code=404, detail={"code": "discovery_not_found", "message": "Discovery not found."}
    )


def get_owned(db: Session, user_id: uuid.UUID, discovery_id: uuid.UUID) -> Discovery:
    discovery = db.scalar(
        select(Discovery).where(Discovery.id == discovery_id, Discovery.user_id == user_id)
    )
    if discovery is None:
        raise not_found()
    return discovery


def create(db: Session, user_id: uuid.UUID, payload: DiscoveryCreate) -> Discovery:
    try:
        normalized = normalize_url(payload.url)
    except InvalidUrlError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_url", "message": str(exc)}
        ) from exc
    existing = db.scalar(
        select(Discovery).where(
            Discovery.user_id == user_id,
            Discovery.canonical_url_hash == normalized.canonical_url_hash,
        )
    )
    if existing is not None:
        if existing.canonical_url != normalized.canonical_url:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "canonical_hash_collision",
                    "message": "This URL could not be saved safely.",
                },
            )
        raise HTTPException(
            status_code=409,
            detail={
                "code": "duplicate_discovery",
                "message": "This Discovery is already in your library.",
            },
        )
    discovery = Discovery(
        user_id=user_id,
        original_url=normalized.original_url,
        canonical_url=normalized.canonical_url,
        canonical_url_hash=normalized.canonical_url_hash,
        normalization_version=normalized.normalization_version,
        platform=normalized.platform.value,
        custom_title=payload.custom_title,
        personal_note=payload.personal_note,
        save_reason=payload.save_reason,
    )
    db.add(discovery)
    ensure_record(discovery)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "duplicate_discovery",
                "message": "This Discovery is already in your library.",
            },
        ) from exc
    db.refresh(discovery)
    return discovery


def list_owned(
    db: Session,
    user_id: uuid.UUID,
    *,
    q: str | None,
    platform: Platform | None,
    archived: bool,
    favourite: bool | None,
    limit: int,
    offset: int,
) -> tuple[list[Discovery], int]:
    conditions = [Discovery.user_id == user_id]
    conditions.append(
        Discovery.archived_at.is_not(None) if archived else Discovery.archived_at.is_(None)
    )
    if platform is not None:
        conditions.append(Discovery.platform == platform.value)
    if favourite is not None:
        conditions.append(Discovery.is_favourite == favourite)
    if q and (term := q.strip()):
        pattern = f"%{term}%"
        conditions.append(
            or_(
                Discovery.custom_title.ilike(pattern),
                Discovery.personal_note.ilike(pattern),
                Discovery.original_url.ilike(pattern),
                Discovery.canonical_url.ilike(pattern),
            )
        )
    total = db.scalar(select(func.count()).select_from(Discovery).where(*conditions)) or 0
    results = list(
        db.scalars(
            select(Discovery)
            .where(*conditions)
            .order_by(Discovery.created_at.desc(), Discovery.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return results, total


def update(db: Session, discovery: Discovery, payload: DiscoveryUpdate) -> Discovery:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(discovery, field, value)
    discovery.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(discovery)
    return discovery


def set_archived(db: Session, discovery: Discovery, archived: bool) -> Discovery:
    if archived and discovery.archived_at is None:
        discovery.archived_at = datetime.now(UTC)
    elif not archived and discovery.archived_at is not None:
        discovery.archived_at = None
    else:
        return discovery
    discovery.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(discovery)
    return discovery


def delete(db: Session, discovery: Discovery) -> None:
    db.delete(discovery)
    db.commit()
