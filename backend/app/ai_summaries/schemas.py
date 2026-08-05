import unicodedata
from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def clean(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    if any(ord(char) < 32 and char not in "\t\n\r" for char in value):
        raise ValueError("control characters are not allowed")
    return " ".join(value.split())


class EntityType(StrEnum):
    person = "person"
    organization = "organization"
    place = "place"
    product = "product"
    work = "work"
    event = "event"
    other = "other"


class SummaryEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    type: EntityType
    _clean = field_validator("name")(clean)


class SummaryOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str | None = Field(default=None, min_length=1, max_length=600)
    key_points: list[str] = Field(default_factory=list, max_length=5)
    topics: list[str] = Field(default_factory=list, max_length=8)
    entities: list[SummaryEntity] = Field(default_factory=list, max_length=10)
    language: str = Field(
        min_length=2, max_length=35, pattern=r"^(und|[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*)$"
    )
    confidence: float = Field(ge=0, le=1)
    insufficiency_reason: str | None = Field(default=None, min_length=1, max_length=240)

    @field_validator("summary", "insufficiency_reason")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return clean(value) if value is not None else None

    @field_validator("key_points")
    @classmethod
    def clean_points(cls, values: list[str]) -> list[str]:
        return cls._dedupe(values, 240)

    @field_validator("topics")
    @classmethod
    def clean_topics(cls, values: list[str]) -> list[str]:
        return cls._dedupe(values, 60)

    @staticmethod
    def _dedupe(values: list[str], limit: int) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for raw in values:
            value = clean(raw)
            if not value or len(value) > limit:
                raise ValueError("invalid collection item")
            key = value.casefold()
            if key not in seen:
                seen.add(key)
                result.append(value)
        return result

    @model_validator(mode="after")
    def valid_shape(self) -> Self:
        if self.summary is None:
            if self.key_points or self.topics or self.entities or not self.insufficiency_reason:
                raise ValueError("insufficient output must contain only a reason")
        elif self.insufficiency_reason is not None:
            raise ValueError("successful output cannot contain an insufficiency reason")
        return self


class SummaryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    description: str | None = None
    site_name: str | None = None
    creator_or_publisher: str | None = None
    published_date: str | None = None
    platform: str
    canonical_hostname: str


class PublicError(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class PublicSummary(BaseModel):
    status: str
    summary: str | None = None
    key_points: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    entities: list[SummaryEntity] = Field(default_factory=list)
    language: str | None = None
    confidence: float | None = None
    insufficiency_reason: str | None = None
    generated_at: datetime | None = None
    last_attempted_at: datetime | None = None
    is_regenerating: bool = False
    last_attempt_error: PublicError | None = None
    error: PublicError | None = None
    can_generate: bool = False
    can_retry: bool = False
    can_regenerate: bool = False
    retry_after_seconds: int | None = None


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    use_personal_note: bool = False

    @field_validator("use_personal_note")
    @classmethod
    def no_note(cls, value: bool) -> bool:
        if value:
            raise ValueError("note context is not supported")
        return value


class RegenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: bool

    @field_validator("confirm")
    @classmethod
    def confirmed(cls, value: bool) -> bool:
        if not value:
            raise ValueError("confirmation is required")
        return value
