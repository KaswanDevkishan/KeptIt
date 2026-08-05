"""create metadata records

Revision ID: 20260805_0004
Revises: 20260805_0003
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260805_0004"
down_revision: str | None = "20260805_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metadata_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("discovery_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("site_name", sa.String(200), nullable=True),
        sa.Column("creator_or_publisher", sa.String(300), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(80), nullable=True),
        sa.Column("failure_message_safe", sa.String(500), nullable=True),
        sa.Column("provider", sa.String(50), server_default="pending", nullable=False),
        sa.Column("metadata_version", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'succeeded', 'failed', 'unsupported')",
            name="ck_metadata_records_status_allowed",
        ),
        sa.CheckConstraint("metadata_version > 0", name="ck_metadata_records_version_positive"),
        sa.CheckConstraint(
            "failure_message_safe IS NULL OR length(failure_message_safe) <= 500",
            name="ck_metadata_records_failure_message_length",
        ),
        sa.ForeignKeyConstraint(
            ["discovery_id"],
            ["discoveries.id"],
            name="fk_metadata_records_discovery_id_discoveries",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_metadata_records"),
        sa.UniqueConstraint("discovery_id", name="uq_metadata_records_discovery_id"),
    )
    op.create_index(
        "ix_metadata_records_status_last_attempted",
        "metadata_records",
        ["status", "last_attempted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_metadata_records_status_last_attempted", table_name="metadata_records")
    op.drop_table("metadata_records")
