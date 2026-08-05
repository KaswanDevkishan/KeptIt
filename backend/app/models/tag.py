import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import User, utc_now


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (
        CheckConstraint("length(name) > 0", name="ck_tags_name_nonempty"),
        CheckConstraint("length(normalized_name) > 0", name="ck_tags_normalized_name_nonempty"),
        UniqueConstraint("user_id", "normalized_name", name="uq_tags_user_id_normalized_name"),
        UniqueConstraint("user_id", "id", name="uq_tags_user_id_id"),
        Index("ix_tags_user_normalized_name_id", "user_id", "normalized_name", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", name="fk_tags_user_id_users"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    owner: Mapped[User] = relationship(back_populates="tags")
    memberships: Mapped[list["DiscoveryTag"]] = relationship(
        back_populates="tag",
        cascade="all, delete-orphan",
        passive_deletes=True,
        overlaps="owner,tag_memberships",
    )


class DiscoveryTag(Base):
    __tablename__ = "discovery_tags"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "tag_id"],
            ["tags.user_id", "tags.id"],
            name="fk_discovery_tags_user_tag",
            ondelete="CASCADE",
        ),
        UniqueConstraint("tag_id", "discovery_id", name="uq_discovery_tags_tag_id_discovery_id"),
        Index("ix_discovery_tags_user_discovery_tag", "user_id", "discovery_id", "tag_id"),
        Index("ix_discovery_tags_user_tag_created_id", "user_id", "tag_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", name="fk_discovery_tags_user_id_users"),
        nullable=False,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    discovery_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "discoveries.id", ondelete="CASCADE", name="fk_discovery_tags_discovery_id_discoveries"
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    owner: Mapped[User] = relationship(back_populates="tag_memberships", overlaps="memberships,tag")
    tag: Mapped[Tag] = relationship(back_populates="memberships", overlaps="owner,tag_memberships")
    discovery: Mapped["Discovery"] = relationship(back_populates="tag_memberships")


from app.models.discovery import Discovery  # noqa: E402
