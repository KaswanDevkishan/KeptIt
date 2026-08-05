"""create discovery embeddings

Revision ID: 20260805_0008
Revises: 20260805_0007
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "20260805_0008"
down_revision: str | None = "20260805_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "discovery_embeddings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("discovery_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("document_version", sa.String(100), nullable=False),
        sa.Column("input_fingerprint", sa.LargeBinary(32), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True)),
        sa.Column("last_attempted_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(50)),
        sa.Column("failure_message_safe", sa.String(240)),
        sa.Column("usage_tokens", sa.Integer()),
        sa.Column("estimated_cost_minor_units", sa.BigInteger()),
        sa.Column("retry_count", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True)),
        sa.Column("processing_started_at", sa.DateTime(timezone=True)),
        sa.Column("processing_lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("generation_token", sa.Uuid()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending','processing','succeeded','failed','unsupported','stale')",
            name="ck_discovery_embeddings_status_allowed",
        ),
        sa.CheckConstraint(
            "embedding_dimension > 0", name="ck_discovery_embeddings_dimension_positive"
        ),
        sa.CheckConstraint(
            "length(input_fingerprint) = 32", name="ck_discovery_embeddings_fingerprint_length"
        ),
        sa.CheckConstraint(
            "usage_tokens IS NULL OR usage_tokens >= 0",
            name="ck_discovery_embeddings_usage_nonnegative",
        ),
        sa.CheckConstraint(
            "estimated_cost_minor_units IS NULL OR estimated_cost_minor_units >= 0",
            name="ck_discovery_embeddings_cost_nonnegative",
        ),
        sa.CheckConstraint("retry_count >= 0", name="ck_discovery_embeddings_retry_nonnegative"),
        sa.ForeignKeyConstraint(
            ["discovery_id"],
            ["discoveries.id"],
            ondelete="CASCADE",
            name="fk_discovery_embeddings_discovery_id_discoveries",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_discovery_embeddings"),
        sa.UniqueConstraint("discovery_id", name="uq_discovery_embeddings_discovery_id"),
    )
    op.create_index(
        "ix_discovery_embeddings_runnable",
        "discovery_embeddings",
        ["status", "next_retry_at", "created_at"],
    )
    op.create_index(
        "ix_discovery_embeddings_stale_lease",
        "discovery_embeddings",
        ["processing_lease_expires_at"],
        postgresql_where=sa.text("status = 'processing'"),
    )
    op.create_index(
        "ix_discovery_embeddings_provider_model_status",
        "discovery_embeddings",
        ["provider", "model", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_discovery_embeddings_provider_model_status", table_name="discovery_embeddings"
    )
    op.drop_index("ix_discovery_embeddings_stale_lease", table_name="discovery_embeddings")
    op.drop_index("ix_discovery_embeddings_runnable", table_name="discovery_embeddings")
    op.drop_table("discovery_embeddings")
    # The extension may be shared, so downgrade deliberately leaves it installed.
