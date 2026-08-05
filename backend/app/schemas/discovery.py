import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

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
    metadata_record: "PublicMetadata | None" = Field(
        default=None, validation_alias="metadata_record", serialization_alias="metadata"
    )
    tags: list["TagSummary"] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def display_title(self) -> str:
        if self.custom_title:
            return self.custom_title
        if self.metadata_record and self.metadata_record.title:
            return self.metadata_record.title
        from urllib.parse import urlsplit

        return urlsplit(self.original_url).hostname or self.original_url


class PublicMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    title: str | None
    description: str | None
    site_name: str | None
    creator_or_publisher: str | None
    thumbnail_url: str | None
    published_at: datetime | None
    fetched_at: datetime | None
    last_attempted_at: datetime | None
    failure_code: str | None
    failure_message_safe: str | None
    provider: str
    metadata_version: int


class DiscoveryList(BaseModel):
    results: list[PublicDiscovery]
    total: int
    limit: int
    offset: int


from app.schemas.tag import TagSummary  # noqa: E402
