import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.urls import Platform


def optional_text(value: object) -> object:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    return stripped or None


class DiscoveryCreate(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    custom_title: str | None = Field(default=None, max_length=300)
    personal_note: str | None = Field(default=None, max_length=10_000)
    save_reason: str | None = Field(default=None, max_length=500)

    _normalize_optional = field_validator(
        "custom_title", "personal_note", "save_reason", mode="before"
    )(optional_text)


class DiscoveryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    custom_title: str | None = Field(default=None, max_length=300)
    personal_note: str | None = Field(default=None, max_length=10_000)
    save_reason: str | None = Field(default=None, max_length=500)
    is_favourite: bool | None = None

    _normalize_optional = field_validator(
        "custom_title", "personal_note", "save_reason", mode="before"
    )(optional_text)


class PublicDiscovery(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_url: str
    canonical_url: str
    platform: Platform
    custom_title: str | None
    personal_note: str | None
    save_reason: str | None
    is_favourite: bool
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DiscoveryList(BaseModel):
    results: list[PublicDiscovery]
    total: int
    limit: int
    offset: int
