import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base
from app.models.user import utc_now

if TYPE_CHECKING:
    from app.models.discovery import Discovery

json_type = JSON().with_variant(JSONB(), "postgresql")


class AISummary(Base):
    __tablename__ = "ai_summaries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','processing','succeeded','failed','unsupported',"
            "'insufficient_data')",
            name="ck_ai_summaries_status_allowed",
        ),
        CheckConstraint(
            "summary IS NULL OR length(summary) BETWEEN 1 AND 600",
            name="ck_ai_summaries_summary_length",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_ai_summaries_confidence_bounds",
        ),
        CheckConstraint(
            "input_fingerprint IS NULL OR length(input_fingerprint) = 32",
            name="ck_ai_summaries_fingerprint_length",
        ),
        CheckConstraint(
            "usage_input_tokens IS NULL OR usage_input_tokens >= 0",
            name="ck_ai_summaries_input_tokens_nonnegative",
        ),
        CheckConstraint(
            "usage_output_tokens IS NULL OR usage_output_tokens >= 0",
            name="ck_ai_summaries_output_tokens_nonnegative",
        ),
        CheckConstraint(
            "estimated_cost_minor_units IS NULL OR estimated_cost_minor_units >= 0",
            name="ck_ai_summaries_cost_nonnegative",
        ),
        CheckConstraint("retry_count >= 0", name="ck_ai_summaries_retry_count_nonnegative"),
        UniqueConstraint("discovery_id", name="uq_ai_summaries_discovery_id"),
        Index("ix_ai_summaries_status_updated", "status", "updated_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    discovery_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discoveries.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    provider: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    summary: Mapped[str | None] = mapped_column(String(600))
    key_points: Mapped[list[str]] = mapped_column(MutableList.as_mutable(json_type), default=list)
    topics: Mapped[list[str]] = mapped_column(MutableList.as_mutable(json_type), default=list)
    entities: Mapped[list[dict[str, Any]]] = mapped_column(
        MutableList.as_mutable(json_type), default=list
    )
    language: Mapped[str | None] = mapped_column(String(35))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    insufficiency_reason: Mapped[str | None] = mapped_column(String(240))
    input_fingerprint: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(64))
    failure_message_safe: Mapped[str | None] = mapped_column(String(240))
    usage_input_tokens: Mapped[int | None] = mapped_column(Integer)
    usage_output_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_minor_units: Mapped[int | None] = mapped_column(BigInteger)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    generation_token: Mapped[uuid.UUID | None] = mapped_column()
    retry_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    is_regenerating: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    discovery: Mapped["Discovery"] = relationship(back_populates="ai_summary")


class AISummaryIdempotencyKey(Base):
    __tablename__ = "ai_summary_idempotency_keys"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "action", "discovery_id", "key_hash", name="uq_ai_summary_idempotency_scope"
        ),
        Index("ix_ai_summary_idempotency_expires", "expires_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    discovery_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discoveries.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    payload_fingerprint: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    result_http_status: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
