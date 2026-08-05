import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import utc_now

if TYPE_CHECKING:
    from app.models.discovery import Discovery


class DiscoveryEmbedding(Base):
    __tablename__ = "discovery_embeddings"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','processing','succeeded','failed','unsupported','stale')",
            name="ck_discovery_embeddings_status_allowed",
        ),
        CheckConstraint(
            "embedding_dimension > 0", name="ck_discovery_embeddings_dimension_positive"
        ),
        CheckConstraint(
            "length(input_fingerprint) = 32", name="ck_discovery_embeddings_fingerprint_length"
        ),
        CheckConstraint(
            "usage_tokens IS NULL OR usage_tokens >= 0",
            name="ck_discovery_embeddings_usage_nonnegative",
        ),
        CheckConstraint(
            "estimated_cost_minor_units IS NULL OR estimated_cost_minor_units >= 0",
            name="ck_discovery_embeddings_cost_nonnegative",
        ),
        CheckConstraint("retry_count >= 0", name="ck_discovery_embeddings_retry_nonnegative"),
        UniqueConstraint("discovery_id", name="uq_discovery_embeddings_discovery_id"),
        Index("ix_discovery_embeddings_runnable", "status", "next_retry_at", "created_at"),
        Index("ix_discovery_embeddings_stale_lease", "processing_lease_expires_at"),
        Index("ix_discovery_embeddings_provider_model_status", "provider", "model", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    discovery_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discoveries.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    document_version: Mapped[str] = mapped_column(String(100), nullable=False)
    input_fingerprint: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(50))
    failure_message_safe: Mapped[str | None] = mapped_column(String(240))
    usage_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_minor_units: Mapped[int | None] = mapped_column(BigInteger)
    retry_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    generation_token: Mapped[uuid.UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    discovery: Mapped["Discovery"] = relationship(back_populates="embedding_record")
