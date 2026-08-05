"""create spaces

Revision ID: 20260805_0005
Revises: 20260805_0004
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260805_0005"
down_revision: str | None = "20260805_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "spaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("normalized_name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("char_length(name) > 0", name="ck_spaces_name_nonempty"),
        sa.CheckConstraint(
            "char_length(normalized_name) > 0", name="ck_spaces_normalized_name_nonempty"
        ),
        sa.CheckConstraint(
            "description IS NULL OR char_length(description) <= 500",
            name="ck_spaces_description_length",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_spaces_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_spaces"),
        sa.UniqueConstraint("user_id", "normalized_name", name="uq_spaces_user_id_normalized_name"),
        sa.UniqueConstraint("user_id", "id", name="uq_spaces_user_id_id"),
    )
    op.create_index(
        "ix_spaces_user_updated_id",
        "spaces",
        ["user_id", sa.text("updated_at DESC"), sa.text("id DESC")],
    )

    op.create_table(
        "space_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("space_id", sa.Uuid(), nullable=False),
        sa.Column("discovery_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_space_memberships_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "space_id"],
            ["spaces.user_id", "spaces.id"],
            name="fk_space_memberships_user_space",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["discovery_id"],
            ["discoveries.id"],
            name="fk_space_memberships_discovery_id_discoveries",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_space_memberships"),
        sa.UniqueConstraint(
            "space_id", "discovery_id", name="uq_space_memberships_space_id_discovery_id"
        ),
    )
    op.create_index(
        "ix_space_memberships_user_space_created_id",
        "space_memberships",
        ["user_id", "space_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_space_memberships_user_discovery_space",
        "space_memberships",
        ["user_id", "discovery_id", "space_id"],
    )
    op.execute(
        """
        CREATE FUNCTION enforce_space_membership_discovery_owner()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM discoveries
                WHERE id = NEW.discovery_id AND user_id = NEW.user_id
            ) THEN
                RAISE EXCEPTION 'space membership ownership mismatch'
                    USING ERRCODE = '23514', CONSTRAINT = 'ck_space_memberships_discovery_owner';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_space_memberships_discovery_owner
        BEFORE INSERT OR UPDATE OF user_id, discovery_id ON space_memberships
        FOR EACH ROW EXECUTE FUNCTION enforce_space_membership_discovery_owner()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_space_memberships_discovery_owner ON space_memberships")
    op.execute("DROP FUNCTION enforce_space_membership_discovery_owner()")
    op.drop_index("ix_space_memberships_user_discovery_space", table_name="space_memberships")
    op.drop_index("ix_space_memberships_user_space_created_id", table_name="space_memberships")
    op.drop_table("space_memberships")
    op.drop_index("ix_spaces_user_updated_id", table_name="spaces")
    op.drop_table("spaces")
