import unicodedata
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def clean_tag_name(value: object) -> object:
    if not isinstance(value, str):
        return value
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError("Control characters are not allowed.")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Enter a Tag name.")
    return cleaned


class TagCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=50)
    _clean = field_validator("name", mode="before")(clean_tag_name)


class TagUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=50)
    _clean = field_validator("name", mode="before")(clean_tag_name)


class TagSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str


class PublicTag(TagSummary):
    discovery_count: int = 0
    created_at: datetime
    updated_at: datetime


class TagList(BaseModel):
    items: list[PublicTag]
    next_cursor: str | None


class PublicTagMembership(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tag_id: uuid.UUID
    discovery_id: uuid.UUID
    created_at: datetime


class TagDiscoveryList(BaseModel):
    items: list["PublicDiscovery"]
    next_cursor: str | None


from app.schemas.discovery import PublicDiscovery  # noqa: E402
