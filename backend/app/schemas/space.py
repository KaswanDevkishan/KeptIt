import unicodedata
import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.discovery import PublicDiscovery


def clean_text(value: object, *, empty_to_none: bool) -> object:
    if not isinstance(value, str):
        return value
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError("Control characters are not allowed.")
    cleaned = value.strip()
    if empty_to_none and not cleaned:
        return None
    return cleaned


class SpaceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> object:
        return clean_text(value, empty_to_none=False)

    @field_validator("description", mode="before")
    @classmethod
    def validate_description(cls, value: object) -> object:
        return clean_text(value, empty_to_none=True)


class SpaceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> object:
        if value is None:
            raise ValueError("Name cannot be null.")
        return clean_text(value, empty_to_none=False)

    @field_validator("description", mode="before")
    @classmethod
    def validate_description(cls, value: object) -> object:
        return clean_text(value, empty_to_none=True)

    @model_validator(mode="after")
    def require_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field is required.")
        return self


class PublicSpace(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    discovery_count: int = 0
    created_at: datetime
    updated_at: datetime


class SpaceList(BaseModel):
    items: list[PublicSpace]
    next_cursor: str | None


class PublicSpaceMembership(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    space_id: uuid.UUID
    discovery_id: uuid.UUID
    created_at: datetime


class SpaceDiscoveryList(BaseModel):
    items: list[PublicDiscovery]
    next_cursor: str | None
