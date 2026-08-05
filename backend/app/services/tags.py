import base64
import hashlib
import hmac
import json
import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.discovery import Discovery
from app.models.tag import DiscoveryTag, Tag
from app.models.user import User
from app.schemas.tag import TagCreate, TagUpdate

MAX_TAGS_PER_USER = 500
MAX_TAGS_PER_DISCOVERY = 20


def normalize_name(name: str) -> str:
    return unicodedata.normalize("NFKC", name).casefold()


def not_found() -> HTTPException:
    return HTTPException(
        status_code=404, detail={"code": "resource_not_found", "message": "Resource not found."}
    )


def conflict() -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "code": "tag_name_conflict",
            "message": "You already have a Tag with that name.",
            "fields": {"name": "Choose a different Tag name."},
        },
    )


def limit_error(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": code, "message": message})


def get_owned(db: Session, user_id: uuid.UUID, tag_id: uuid.UUID) -> Tag:
    tag = db.scalar(select(Tag).where(Tag.user_id == user_id, Tag.id == tag_id))
    if tag is None:
        raise not_found()
    return tag


def create_tag(db: Session, user_id: uuid.UUID, payload: TagCreate) -> Tag:
    db.scalar(select(User).where(User.id == user_id).with_for_update())
    if (
        db.scalar(select(func.count()).select_from(Tag).where(Tag.user_id == user_id)) or 0
    ) >= MAX_TAGS_PER_USER:
        raise limit_error("tag_limit_reached", "You have reached the Tag limit.")
    normalized = normalize_name(payload.name)
    if db.scalar(select(Tag.id).where(Tag.user_id == user_id, Tag.normalized_name == normalized)):
        raise conflict()
    tag = Tag(user_id=user_id, name=payload.name, normalized_name=normalized)
    db.add(tag)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict() from exc
    db.refresh(tag)
    return tag


def rename_tag(db: Session, tag: Tag, payload: TagUpdate) -> Tag:
    normalized = normalize_name(payload.name)
    if payload.name == tag.name and normalized == tag.normalized_name:
        return tag
    if db.scalar(
        select(Tag.id).where(
            Tag.user_id == tag.user_id, Tag.normalized_name == normalized, Tag.id != tag.id
        )
    ):
        raise conflict()
    tag.name, tag.normalized_name, tag.updated_at = payload.name, normalized, datetime.now(UTC)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict() from exc
    db.refresh(tag)
    return tag


def delete_tag(db: Session, tag: Tag) -> None:
    db.delete(tag)
    db.commit()


def _cursor(offset: int, context: str) -> str:
    payload = json.dumps({"offset": offset, "context": context}, separators=(",", ":")).encode()
    signature = hmac.new(
        get_settings().spaces_cursor_secret.encode(), payload, hashlib.sha256
    ).digest()[:16]
    return base64.urlsafe_b64encode(payload + signature).decode().rstrip("=")


def _decode(cursor: str | None, context: str) -> int:
    if cursor is None:
        return 0
    try:
        value = base64.urlsafe_b64decode((cursor + "=" * (-len(cursor) % 4)).encode())
        payload, signature = value[:-16], value[-16:]
        expected = hmac.new(
            get_settings().spaces_cursor_secret.encode(), payload, hashlib.sha256
        ).digest()[:16]
        decoded = json.loads(payload)
        if (
            not hmac.compare_digest(signature, expected)
            or decoded["context"] != context
            or int(decoded["offset"]) < 0
        ):
            raise ValueError
        return int(decoded["offset"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_cursor", "message": "The pagination cursor is invalid."},
        ) from exc


def list_tags(
    db: Session,
    user_id: uuid.UUID,
    *,
    limit: int,
    cursor: str | None,
    q: str | None,
    sort: Literal["name_asc", "updated_desc"],
) -> tuple[list[tuple[Tag, int]], str | None]:
    search = normalize_name(q.strip()) if q else ""
    context = f"tags:{sort}:{search}"
    offset = _decode(cursor, context)
    count = func.count(DiscoveryTag.id).label("discovery_count")
    query = (
        select(Tag, count)
        .outerjoin(
            DiscoveryTag, (DiscoveryTag.tag_id == Tag.id) & (DiscoveryTag.user_id == user_id)
        )
        .where(Tag.user_id == user_id)
        .group_by(Tag.id)
    )
    if search:
        query = query.where(Tag.normalized_name.contains(search))
    query = (
        query.order_by(Tag.normalized_name.asc(), Tag.id.asc())
        if sort == "name_asc"
        else query.order_by(Tag.updated_at.desc(), Tag.id.desc())
    )
    rows = list(db.execute(query.offset(offset).limit(limit + 1)).tuples())
    return rows[:limit], _cursor(offset + limit, context) if len(rows) > limit else None


def attach_tag_to_discovery(
    db: Session, user_id: uuid.UUID, tag_id: uuid.UUID, discovery_id: uuid.UUID
) -> tuple[DiscoveryTag, bool]:
    get_owned(db, user_id, tag_id)
    discovery = db.scalar(
        select(Discovery)
        .where(Discovery.user_id == user_id, Discovery.id == discovery_id)
        .with_for_update()
    )
    if discovery is None:
        raise not_found()
    existing = db.scalar(
        select(DiscoveryTag).where(
            DiscoveryTag.user_id == user_id,
            DiscoveryTag.tag_id == tag_id,
            DiscoveryTag.discovery_id == discovery_id,
        )
    )
    if existing:
        return existing, False
    if (
        db.scalar(
            select(func.count())
            .select_from(DiscoveryTag)
            .where(DiscoveryTag.user_id == user_id, DiscoveryTag.discovery_id == discovery_id)
        )
        or 0
    ) >= MAX_TAGS_PER_DISCOVERY:
        raise limit_error(
            "discovery_tag_limit_reached", "This Discovery has reached the Tag limit."
        )
    membership = DiscoveryTag(user_id=user_id, tag_id=tag_id, discovery_id=discovery_id)
    db.add(membership)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(DiscoveryTag).where(
                DiscoveryTag.user_id == user_id,
                DiscoveryTag.tag_id == tag_id,
                DiscoveryTag.discovery_id == discovery_id,
            )
        )
        if existing:
            return existing, False
        raise not_found() from None
    db.refresh(membership)
    return membership, True


def detach_tag_from_discovery(
    db: Session, user_id: uuid.UUID, tag_id: uuid.UUID, discovery_id: uuid.UUID
) -> None:
    get_owned(db, user_id, tag_id)
    if (
        db.scalar(
            select(Discovery.id).where(Discovery.user_id == user_id, Discovery.id == discovery_id)
        )
        is None
    ):
        raise not_found()
    membership = db.scalar(
        select(DiscoveryTag).where(
            DiscoveryTag.user_id == user_id,
            DiscoveryTag.tag_id == tag_id,
            DiscoveryTag.discovery_id == discovery_id,
        )
    )
    if membership is None:
        raise not_found()
    db.delete(membership)
    db.commit()


def list_tag_discoveries(
    db: Session,
    user_id: uuid.UUID,
    tag_id: uuid.UUID,
    *,
    limit: int,
    cursor: str | None,
    archive: Literal["active", "archived", "all"],
) -> tuple[list[Discovery], str | None]:
    get_owned(db, user_id, tag_id)
    context = f"tag-discoveries:{tag_id}:{archive}"
    offset = _decode(cursor, context)
    conditions = [
        DiscoveryTag.user_id == user_id,
        DiscoveryTag.tag_id == tag_id,
        Discovery.user_id == user_id,
    ]
    if archive == "active":
        conditions.append(Discovery.archived_at.is_(None))
    elif archive == "archived":
        conditions.append(Discovery.archived_at.is_not(None))
    items = list(
        db.scalars(
            select(Discovery)
            .join(DiscoveryTag, DiscoveryTag.discovery_id == Discovery.id)
            .where(*conditions)
            .order_by(DiscoveryTag.created_at.desc(), DiscoveryTag.id.desc())
            .offset(offset)
            .limit(limit + 1)
        )
    )
    return items[:limit], _cursor(offset + limit, context) if len(items) > limit else None
