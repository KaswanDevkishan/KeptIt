"""create AI summaries

Revision ID: 20260805_0006
Revises: 20260805_0005
"""
# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260805_0006"
down_revision: str | None = "20260805_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_summaries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("discovery_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending", nullable=False),
        sa.Column("provider", sa.String(64)),
        sa.Column("model", sa.String(128)),
        sa.Column("prompt_version", sa.String(64)),
        sa.Column("summary", sa.String(600)),
        sa.Column(
            "key_points", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "topics", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "entities", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("language", sa.String(35)),
        sa.Column("confidence", sa.Numeric(4, 3)),
        sa.Column("insufficiency_reason", sa.String(240)),
        sa.Column("input_fingerprint", sa.LargeBinary(32)),
        sa.Column("generated_at", sa.DateTime(timezone=True)),
        sa.Column("last_attempted_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(64)),
        sa.Column("failure_message_safe", sa.String(240)),
        sa.Column("usage_input_tokens", sa.Integer()),
        sa.Column("usage_output_tokens", sa.Integer()),
        sa.Column("estimated_cost_minor_units", sa.BigInteger()),
        sa.Column("available_at", sa.DateTime(timezone=True)),
        sa.Column("processing_started_at", sa.DateTime(timezone=True)),
        sa.Column("processing_lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("generation_token", sa.Uuid()),
        sa.Column("retry_count", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("is_regenerating", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending','processing','succeeded','failed','unsupported','insufficient_data')",
            name="ck_ai_summaries_status_allowed",
        ),
        sa.CheckConstraint(
            "summary IS NULL OR char_length(summary) BETWEEN 1 AND 600",
            name="ck_ai_summaries_summary_length",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name="ck_ai_summaries_confidence_bounds",
        ),
        sa.CheckConstraint(
            "input_fingerprint IS NULL OR octet_length(input_fingerprint) = 32",
            name="ck_ai_summaries_fingerprint_length",
        ),
        sa.CheckConstraint(
            "usage_input_tokens IS NULL OR usage_input_tokens >= 0",
            name="ck_ai_summaries_input_tokens_nonnegative",
        ),
        sa.CheckConstraint(
            "usage_output_tokens IS NULL OR usage_output_tokens >= 0",
            name="ck_ai_summaries_output_tokens_nonnegative",
        ),
        sa.CheckConstraint(
            "estimated_cost_minor_units IS NULL OR estimated_cost_minor_units >= 0",
            name="ck_ai_summaries_cost_nonnegative",
        ),
        sa.CheckConstraint("retry_count >= 0", name="ck_ai_summaries_retry_count_nonnegative"),
        sa.ForeignKeyConstraint(
            ["discovery_id"],
            ["discoveries.id"],
            ondelete="CASCADE",
            name="fk_ai_summaries_discovery_id_discoveries",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_summaries"),
        sa.UniqueConstraint("discovery_id", name="uq_ai_summaries_discovery_id"),
    )
    op.create_index("ix_ai_summaries_status_updated", "ai_summaries", ["status", "updated_at"])
    op.create_index(
        "ix_ai_summaries_runnable",
        "ai_summaries",
        ["available_at", "created_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_ai_summaries_expired_lease",
        "ai_summaries",
        ["processing_lease_expires_at"],
        postgresql_where=sa.text("status = 'processing'"),
    )
    op.create_table(
        "ai_summary_idempotency_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("discovery_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("key_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("payload_fingerprint", sa.LargeBinary(32), nullable=False),
        sa.Column("result_http_status", sa.SmallInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN ('generate','regenerate')", name="ck_ai_summary_idempotency_action"
        ),
        sa.CheckConstraint(
            "octet_length(key_hash) = 32 AND octet_length(payload_fingerprint) = 32",
            name="ck_ai_summary_idempotency_hash_lengths",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_ai_summary_idempotency_user"
        ),
        sa.ForeignKeyConstraint(
            ["discovery_id"],
            ["discoveries.id"],
            ondelete="CASCADE",
            name="fk_ai_summary_idempotency_discovery",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ai_summary_idempotency_keys"),
        sa.UniqueConstraint(
            "user_id", "action", "discovery_id", "key_hash", name="uq_ai_summary_idempotency_scope"
        ),
    )
    op.create_index(
        "ix_ai_summary_idempotency_expires", "ai_summary_idempotency_keys", ["expires_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_ai_summary_idempotency_expires", table_name="ai_summary_idempotency_keys")
    op.drop_table("ai_summary_idempotency_keys")
    op.drop_index("ix_ai_summaries_expired_lease", table_name="ai_summaries")
    op.drop_index("ix_ai_summaries_runnable", table_name="ai_summaries")
    op.drop_index("ix_ai_summaries_status_updated", table_name="ai_summaries")
    op.drop_table("ai_summaries")
