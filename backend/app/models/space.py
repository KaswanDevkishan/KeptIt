import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.discovery import Discovery
from app.models.user import User, utc_now


class Space(Base):
    __tablename__ = "spaces"
    __table_args__ = (
        CheckConstraint("length(name) > 0", name="ck_spaces_name_nonempty"),
        CheckConstraint("length(normalized_name) > 0", name="ck_spaces_normalized_name_nonempty"),
        CheckConstraint(
            "description IS NULL OR length(description) <= 500",
            name="ck_spaces_description_length",
        ),
        UniqueConstraint("user_id", "normalized_name", name="uq_spaces_user_id_normalized_name"),
        UniqueConstraint("user_id", "id", name="uq_spaces_user_id_id"),
        Index("ix_spaces_user_updated_id", "user_id", "updated_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", name="fk_spaces_user_id_users"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    owner: Mapped[User] = relationship(back_populates="spaces")
    memberships: Mapped[list["SpaceMembership"]] = relationship(
        back_populates="space",
        cascade="all, delete-orphan",
        passive_deletes=True,
        overlaps="owner,space_memberships",
    )
    discoveries: Mapped[list[Discovery]] = relationship(
        secondary="space_memberships", back_populates="spaces", viewonly=True
    )


class SpaceMembership(Base):
    __tablename__ = "space_memberships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "space_id"],
            ["spaces.user_id", "spaces.id"],
            name="fk_space_memberships_user_space",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "space_id", "discovery_id", name="uq_space_memberships_space_id_discovery_id"
        ),
        Index(
            "ix_space_memberships_user_space_created_id",
            "user_id",
            "space_id",
            "created_at",
            "id",
        ),
        Index("ix_space_memberships_user_discovery_space", "user_id", "discovery_id", "space_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE", name="fk_space_memberships_user_id_users"),
        nullable=False,
    )
    space_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    discovery_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "discoveries.id",
            ondelete="CASCADE",
            name="fk_space_memberships_discovery_id_discoveries",
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    owner: Mapped[User] = relationship(
        back_populates="space_memberships", overlaps="memberships,space"
    )
    space: Mapped[Space] = relationship(
        back_populates="memberships", overlaps="owner,space_memberships"
    )
    discovery: Mapped[Discovery] = relationship(back_populates="memberships")
