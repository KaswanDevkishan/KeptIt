import base64
import hashlib
import hmac
import json
import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.discovery import Discovery
from app.models.space import Space, SpaceMembership
from app.schemas.space import SpaceCreate, SpaceUpdate


def normalize_name(name: str) -> str:
    return unicodedata.normalize("NFKC", name).casefold()


def not_found() -> HTTPException:
    return HTTPException(
        status_code=404, detail={"code": "resource_not_found", "message": "Resource not found."}
    )


def conflict(existing_id: uuid.UUID | None = None) -> HTTPException:
    detail: dict[str, object] = {
        "code": "space_name_conflict",
        "message": "A Space with this name already exists.",
        "fields": {"name": "Choose a different Space name."},
    }
    if existing_id is not None:
        detail["existing_space_id"] = str(existing_id)
    return HTTPException(status_code=409, detail=detail)


def get_owned(db: Session, user_id: uuid.UUID, space_id: uuid.UUID) -> Space:
    space = db.scalar(select(Space).where(Space.user_id == user_id, Space.id == space_id))
    if space is None:
        raise not_found()
    return space


def _existing_name(
    db: Session, user_id: uuid.UUID, normalized_name: str, exclude_id: uuid.UUID | None = None
) -> Space | None:
    query = select(Space).where(Space.user_id == user_id, Space.normalized_name == normalized_name)
    if exclude_id is not None:
        query = query.where(Space.id != exclude_id)
    return db.scalar(query)


def create_space(db: Session, user_id: uuid.UUID, payload: SpaceCreate) -> Space:
    normalized = normalize_name(payload.name)
    if existing := _existing_name(db, user_id, normalized):
        raise conflict(existing.id)
    space = Space(
        user_id=user_id,
        name=payload.name,
        normalized_name=normalized,
        description=payload.description,
    )
    db.add(space)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = _existing_name(db, user_id, normalized)
        raise conflict(existing.id if existing else None) from exc
    db.refresh(space)
    return space


def rename_space(db: Session, space: Space, payload: SpaceUpdate) -> Space:
    changes = payload.model_dump(exclude_unset=True)
    changed = False
    if "name" in changes:
        name = changes["name"]
        normalized = normalize_name(name)
        if name != space.name or normalized != space.normalized_name:
            if existing := _existing_name(db, space.user_id, normalized, space.id):
                raise conflict(existing.id)
            space.name = name
            space.normalized_name = normalized
            changed = True
    if "description" in changes and changes["description"] != space.description:
        space.description = changes["description"]
        changed = True
    if not changed:
        return space
    space.updated_at = datetime.now(UTC)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = _existing_name(db, space.user_id, space.normalized_name, space.id)
        raise conflict(existing.id if existing else None) from exc
    db.refresh(space)
    return space


def delete_space(db: Session, space: Space) -> None:
    db.delete(space)
    db.commit()


def _encode_cursor(offset: int, context: str) -> str:
    payload = json.dumps({"offset": offset, "context": context}, separators=(",", ":")).encode()
    key = get_settings().spaces_cursor_secret.encode()
    signature = hmac.new(key, payload, hashlib.sha256).digest()[:16]
    return base64.urlsafe_b64encode(payload + signature).decode().rstrip("=")


def decode_cursor(cursor: str | None, context: str) -> int:
    if cursor is None:
        return 0
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = base64.urlsafe_b64decode(padded.encode())
        payload, signature = value[:-16], value[-16:]
        expected = hmac.new(
            get_settings().spaces_cursor_secret.encode(), payload, hashlib.sha256
        ).digest()[:16]
        decoded = json.loads(payload)
        if not hmac.compare_digest(signature, expected) or decoded["context"] != context:
            raise ValueError
        offset = int(decoded["offset"])
        if offset < 0:
            raise ValueError
        return offset
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_cursor", "message": "The pagination cursor is invalid."},
        ) from exc


def list_spaces(
    db: Session,
    user_id: uuid.UUID,
    *,
    limit: int,
    cursor: str | None,
    sort: Literal["updated_desc", "name_asc"],
) -> tuple[list[tuple[Space, int]], str | None]:
    offset = decode_cursor(cursor, f"spaces:{sort}")
    count = func.count(SpaceMembership.id).label("discovery_count")
    query = (
        select(Space, count)
        .outerjoin(
            SpaceMembership,
            (SpaceMembership.space_id == Space.id) & (SpaceMembership.user_id == user_id),
        )
        .where(Space.user_id == user_id)
        .group_by(Space.id)
    )
    if sort == "name_asc":
        query = query.order_by(Space.normalized_name.asc(), Space.id.asc())
    else:
        query = query.order_by(Space.updated_at.desc(), Space.id.desc())
    rows = list(db.execute(query.offset(offset).limit(limit + 1)).tuples())
    has_more = len(rows) > limit
    return rows[:limit], _encode_cursor(offset + limit, f"spaces:{sort}") if has_more else None


def add_discovery_to_space(
    db: Session, user_id: uuid.UUID, space_id: uuid.UUID, discovery_id: uuid.UUID
) -> tuple[SpaceMembership, bool]:
    get_owned(db, user_id, space_id)
    discovery = db.scalar(
        select(Discovery).where(Discovery.user_id == user_id, Discovery.id == discovery_id)
    )
    if discovery is None:
        raise not_found()
    existing = db.scalar(
        select(SpaceMembership).where(
            SpaceMembership.user_id == user_id,
            SpaceMembership.space_id == space_id,
            SpaceMembership.discovery_id == discovery_id,
        )
    )
    if existing is not None:
        return existing, False
    membership = SpaceMembership(user_id=user_id, space_id=space_id, discovery_id=discovery_id)
    db.add(membership)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(SpaceMembership).where(
                SpaceMembership.user_id == user_id,
                SpaceMembership.space_id == space_id,
                SpaceMembership.discovery_id == discovery_id,
            )
        )
        if existing is None:
            raise not_found() from None
        return existing, False
    db.refresh(membership)
    return membership, True


def remove_discovery_from_space(
    db: Session, user_id: uuid.UUID, space_id: uuid.UUID, discovery_id: uuid.UUID
) -> None:
    get_owned(db, user_id, space_id)
    discovery_exists = db.scalar(
        select(Discovery.id).where(Discovery.user_id == user_id, Discovery.id == discovery_id)
    )
    if discovery_exists is None:
        raise not_found()
    membership = db.scalar(
        select(SpaceMembership).where(
            SpaceMembership.user_id == user_id,
            SpaceMembership.space_id == space_id,
            SpaceMembership.discovery_id == discovery_id,
        )
    )
    if membership is None:
        raise not_found()
    db.delete(membership)
    db.commit()


def list_space_discoveries(
    db: Session,
    user_id: uuid.UUID,
    space_id: uuid.UUID,
    *,
    limit: int,
    cursor: str | None,
    archive: Literal["active", "archived", "all"],
) -> tuple[list[Discovery], str | None]:
    get_owned(db, user_id, space_id)
    context = f"space-discoveries:{space_id}:{archive}"
    offset = decode_cursor(cursor, context)
    conditions = [
        SpaceMembership.user_id == user_id,
        SpaceMembership.space_id == space_id,
        Discovery.user_id == user_id,
    ]
    if archive == "active":
        conditions.append(Discovery.archived_at.is_(None))
    elif archive == "archived":
        conditions.append(Discovery.archived_at.is_not(None))
    query: Select[tuple[Discovery]] = (
        select(Discovery)
        .join(SpaceMembership, SpaceMembership.discovery_id == Discovery.id)
        .where(*conditions)
        .order_by(SpaceMembership.created_at.desc(), SpaceMembership.id.desc())
        .offset(offset)
        .limit(limit + 1)
    )
    items = list(db.scalars(query))
    has_more = len(items) > limit
    return items[:limit], _encode_cursor(offset + limit, context) if has_more else None
