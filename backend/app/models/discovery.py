import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import User, utc_now

if TYPE_CHECKING:
    from app.models.ai_summary import AISummary
    from app.models.space import Space, SpaceMembership


class Discovery(Base):
    __tablename__ = "discoveries"
    __table_args__ = (
        CheckConstraint(
            "length(original_url) BETWEEN 1 AND 2048", name="ck_discoveries_original_url_length"
        ),
        CheckConstraint(
            "length(canonical_url) BETWEEN 1 AND 2048", name="ck_discoveries_canonical_url_length"
        ),
        CheckConstraint(
            "length(canonical_url_hash) = 32", name="ck_discoveries_canonical_url_hash_length"
        ),
        CheckConstraint(
            "normalization_version > 0", name="ck_discoveries_normalization_version_positive"
        ),
        CheckConstraint(
            "platform IN ('instagram', 'youtube', 'tiktok', 'reddit', 'x', 'github', "
            "'generic_web')",
            name="ck_discoveries_platform_allowed",
        ),
        CheckConstraint(
            "custom_title IS NULL OR length(custom_title) BETWEEN 1 AND 300",
            name="ck_discoveries_custom_title_length",
        ),
        CheckConstraint(
            "personal_note IS NULL OR length(personal_note) BETWEEN 1 AND 10000",
            name="ck_discoveries_personal_note_length",
        ),
        CheckConstraint(
            "save_reason IS NULL OR length(save_reason) BETWEEN 1 AND 500",
            name="ck_discoveries_save_reason_length",
        ),
        UniqueConstraint(
            "user_id", "canonical_url_hash", name="uq_discoveries_user_id_canonical_url_hash"
        ),
        Index("ix_discoveries_user_library", "user_id", "archived_at", "created_at", "id"),
        Index("ix_discoveries_user_platform", "user_id", "platform", "created_at", "id"),
        Index("ix_discoveries_user_favourite", "user_id", "is_favourite", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", name="fk_discoveries_user_id_users"),
        nullable=False,
    )
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    normalization_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    custom_title: Mapped[str | None] = mapped_column(String(300))
    personal_note: Mapped[str | None] = mapped_column(Text)
    save_reason: Mapped[str | None] = mapped_column(String(500))
    is_favourite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    user: Mapped[User] = relationship(back_populates="discoveries")
    metadata_record: Mapped["MetadataRecord | None"] = relationship(
        back_populates="discovery", cascade="all, delete-orphan", uselist=False
    )
    memberships: Mapped[list["SpaceMembership"]] = relationship(
        back_populates="discovery", cascade="all, delete-orphan", passive_deletes=True
    )
    spaces: Mapped[list["Space"]] = relationship(
        secondary="space_memberships", back_populates="discoveries", viewonly=True
    )
    ai_summary: Mapped["AISummary | None"] = relationship(
        back_populates="discovery",
        cascade="all, delete-orphan",
        uselist=False,
        passive_deletes=True,
    )


class MetadataRecord(Base):
    __tablename__ = "metadata_records"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'succeeded', 'failed', 'unsupported')",
            name="ck_metadata_records_status_allowed",
        ),
        CheckConstraint("metadata_version > 0", name="ck_metadata_records_version_positive"),
        CheckConstraint(
            "failure_message_safe IS NULL OR length(failure_message_safe) <= 500",
            name="ck_metadata_records_failure_message_length",
        ),
        UniqueConstraint("discovery_id", name="uq_metadata_records_discovery_id"),
        Index("ix_metadata_records_status_last_attempted", "status", "last_attempted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    discovery_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "discoveries.id",
            ondelete="CASCADE",
            name="fk_metadata_records_discovery_id_discoveries",
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    title: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(String(2000))
    site_name: Mapped[str | None] = mapped_column(String(200))
    creator_or_publisher: Mapped[str | None] = mapped_column(String(300))
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(80))
    failure_message_safe: Mapped[str | None] = mapped_column(String(500))
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    metadata_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    discovery: Mapped[Discovery] = relationship(back_populates="metadata_record")
