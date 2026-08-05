"""create discoveries

Revision ID: 20260805_0003
Revises: 20260805_0002
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260805_0003"
down_revision: str | None = "20260805_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "discoveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("canonical_url_hash", postgresql.BYTEA(), nullable=False),
        sa.Column("normalization_version", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("custom_title", sa.String(300), nullable=True),
        sa.Column("personal_note", sa.Text(), nullable=True),
        sa.Column("save_reason", sa.String(500), nullable=True),
        sa.Column("is_favourite", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "length(original_url) BETWEEN 1 AND 2048", name="ck_discoveries_original_url_length"
        ),
        sa.CheckConstraint(
            "length(canonical_url) BETWEEN 1 AND 2048", name="ck_discoveries_canonical_url_length"
        ),
        sa.CheckConstraint(
            "octet_length(canonical_url_hash) = 32", name="ck_discoveries_canonical_url_hash_length"
        ),
        sa.CheckConstraint(
            "normalization_version > 0", name="ck_discoveries_normalization_version_positive"
        ),
        sa.CheckConstraint(
            "platform IN ('instagram', 'youtube', 'tiktok', 'reddit', 'x', 'github', "
            "'generic_web')",
            name="ck_discoveries_platform_allowed",
        ),
        sa.CheckConstraint(
            "custom_title IS NULL OR length(custom_title) BETWEEN 1 AND 300",
            name="ck_discoveries_custom_title_length",
        ),
        sa.CheckConstraint(
            "personal_note IS NULL OR length(personal_note) BETWEEN 1 AND 10000",
            name="ck_discoveries_personal_note_length",
        ),
        sa.CheckConstraint(
            "save_reason IS NULL OR length(save_reason) BETWEEN 1 AND 500",
            name="ck_discoveries_save_reason_length",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_discoveries_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_discoveries"),
        sa.UniqueConstraint(
            "user_id", "canonical_url_hash", name="uq_discoveries_user_id_canonical_url_hash"
        ),
    )
    op.create_index(
        "ix_discoveries_user_library",
        "discoveries",
        ["user_id", "archived_at", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_discoveries_user_platform",
        "discoveries",
        ["user_id", "platform", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_discoveries_user_favourite",
        "discoveries",
        ["user_id", "is_favourite", sa.text("created_at DESC"), sa.text("id DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_discoveries_user_favourite", table_name="discoveries")
    op.drop_index("ix_discoveries_user_platform", table_name="discoveries")
    op.drop_index("ix_discoveries_user_library", table_name="discoveries")
    op.drop_table("discoveries")
