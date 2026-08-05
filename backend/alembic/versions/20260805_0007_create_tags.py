"""create tags

Revision ID: 20260805_0007
Revises: 20260805_0006
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260805_0007"
down_revision: str | None = "20260805_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("char_length(name) > 0", name="ck_tags_name_nonempty"),
        sa.CheckConstraint(
            "char_length(normalized_name) > 0", name="ck_tags_normalized_name_nonempty"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_tags_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tags"),
        sa.UniqueConstraint("user_id", "normalized_name", name="uq_tags_user_id_normalized_name"),
        sa.UniqueConstraint("user_id", "id", name="uq_tags_user_id_id"),
    )
    op.create_index("ix_tags_user_normalized_name_id", "tags", ["user_id", "normalized_name", "id"])
    op.create_table(
        "discovery_tags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column("discovery_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_discovery_tags_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "tag_id"],
            ["tags.user_id", "tags.id"],
            name="fk_discovery_tags_user_tag",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["discovery_id"],
            ["discoveries.id"],
            name="fk_discovery_tags_discovery_id_discoveries",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_discovery_tags"),
        sa.UniqueConstraint("tag_id", "discovery_id", name="uq_discovery_tags_tag_id_discovery_id"),
    )
    op.create_index(
        "ix_discovery_tags_user_discovery_tag",
        "discovery_tags",
        ["user_id", "discovery_id", "tag_id"],
    )
    op.create_index(
        "ix_discovery_tags_user_tag_created_id",
        "discovery_tags",
        ["user_id", "tag_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.execute("""
        CREATE FUNCTION enforce_discovery_tag_discovery_owner()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM discoveries
                WHERE id = NEW.discovery_id AND user_id = NEW.user_id
            ) THEN
                RAISE EXCEPTION 'discovery tag ownership mismatch'
                    USING ERRCODE = '23514', CONSTRAINT = 'ck_discovery_tags_discovery_owner';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_discovery_tags_discovery_owner
        BEFORE INSERT OR UPDATE OF user_id, discovery_id ON discovery_tags
        FOR EACH ROW EXECUTE FUNCTION enforce_discovery_tag_discovery_owner()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_discovery_tags_discovery_owner ON discovery_tags")
    op.execute("DROP FUNCTION enforce_discovery_tag_discovery_owner()")
    op.drop_index("ix_discovery_tags_user_tag_created_id", table_name="discovery_tags")
    op.drop_index("ix_discovery_tags_user_discovery_tag", table_name="discovery_tags")
    op.drop_table("discovery_tags")
    op.drop_index("ix_tags_user_normalized_name_id", table_name="tags")
    op.drop_table("tags")
