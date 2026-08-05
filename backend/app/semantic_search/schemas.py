import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.discovery import PublicDiscovery
from app.services.urls import Platform


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyRequest(StrictModel):
    pass


class RetryRequest(StrictModel):
    confirm: Literal[True]


class EmbeddingStatus(BaseModel):
    status: Literal[
        "unavailable", "pending", "processing", "succeeded", "failed", "unsupported", "stale"
    ]
    is_searchable: bool
    generated_at: datetime | None
    last_attempted_at: datetime | None
    can_index: bool
    can_retry: bool
    retry_after_seconds: int | None
    error: dict[str, str] | None = None


class SearchFilters(StrictModel):
    platform: list[Platform] = Field(default_factory=list, max_length=8)
    space_id: uuid.UUID | None = None
    tag_id: uuid.UUID | None = None
    is_favourite: bool | None = None
    archive: Literal["active", "archived", "all"] = "active"


class SemanticSearchRequest(StrictModel):
    query: str
    mode: Literal["hybrid", "semantic", "keyword"] = "hybrid"
    filters: SearchFilters = Field(default_factory=SearchFilters)
    limit: int = Field(default=20, ge=1, le=50)
    cursor: str | None = None

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not 2 <= len(normalized) <= 500 or len(normalized.encode()) > 2000 or "\x00" in value:
            raise ValueError("query must be between 2 and 500 characters")
        return normalized


class Relevance(BaseModel):
    score: float
    semantic_similarity: float | None
    keyword_match: bool
    match_reasons: list[str]


class SemanticSearchItem(BaseModel):
    discovery: PublicDiscovery
    relevance: Relevance


class SearchMetadata(BaseModel):
    requested_mode: str
    effective_mode: str
    fallback_reason: str | None
    index_coverage: Literal["none", "partial", "complete"]
    indexed_count: int
    eligible_count: int
    ranking_version: str = "semantic-hybrid-v1"


class SemanticSearchResponse(BaseModel):
    items: list[SemanticSearchItem]
    next_cursor: str | None = None
    search: SearchMetadata


class BackfillRequest(StrictModel):
    limit: int = Field(default=50, ge=1, le=100)
    include_stale: bool = True


class BackfillResponse(BaseModel):
    status: Literal["accepted"] = "accepted"
    requested: int
    queued: int
    skipped_current: int
    skipped_unsupported: int
    remaining_eligible: int
