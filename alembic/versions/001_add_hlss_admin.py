"""add hlss admin support

Revision ID: 001
Revises:
Create Date: 2026-01-14

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_add_hlss_admin"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Schema name
SCHEMA = "eink_llss"


def upgrade() -> None:
    # Create hlss_types table
    op.create_table(
        "hlss_types",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type_id", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("auth_token", sa.String(255), nullable=True),
        sa.Column("default_width", sa.Integer(), nullable=True),
        sa.Column("default_height", sa.Integer(), nullable=True),
        sa.Column("default_bit_depth", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("type_id"),
        schema=SCHEMA,
    )
    op.create_index("idx_hlss_types_type_id", "hlss_types", ["type_id"], schema=SCHEMA)

    # Add new columns to instances table
    op.add_column(
        "instances",
        sa.Column("hlss_type_id", sa.String(50), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "instances",
        sa.Column(
            "hlss_initialized", sa.Boolean(), nullable=False, server_default="false"
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "instances",
        sa.Column("hlss_ready", sa.Boolean(), nullable=False, server_default="false"),
        schema=SCHEMA,
    )
    op.add_column(
        "instances",
        sa.Column(
            "needs_configuration", sa.Boolean(), nullable=False, server_default="false"
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "instances",
        sa.Column("configuration_url", sa.String(500), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "instances",
        sa.Column("display_width", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "instances",
        sa.Column("display_height", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "instances",
        sa.Column("display_bit_depth", sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "instances",
        sa.Column("initialized_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )

    # Add foreign key constraint
    op.create_foreign_key(
        "fk_instances_hlss_type",
        "instances",
        "hlss_types",
        ["hlss_type_id"],
        ["type_id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="SET NULL",
    )

    # Add index on hlss_type_id
    op.create_index(
        "idx_instances_hlss_type_id", "instances", ["hlss_type_id"], schema=SCHEMA
    )


def downgrade() -> None:
    # Remove foreign key constraint
    op.drop_constraint(
        "fk_instances_hlss_type", "instances", schema=SCHEMA, type_="foreignkey"
    )

    # Remove index
    op.drop_index("idx_instances_hlss_type_id", table_name="instances", schema=SCHEMA)

    # Remove columns from instances table
    op.drop_column("instances", "initialized_at", schema=SCHEMA)
    op.drop_column("instances", "display_bit_depth", schema=SCHEMA)
    op.drop_column("instances", "display_height", schema=SCHEMA)
    op.drop_column("instances", "display_width", schema=SCHEMA)
    op.drop_column("instances", "configuration_url", schema=SCHEMA)
    op.drop_column("instances", "needs_configuration", schema=SCHEMA)
    op.drop_column("instances", "hlss_ready", schema=SCHEMA)
    op.drop_column("instances", "hlss_initialized", schema=SCHEMA)
    op.drop_column("instances", "hlss_type_id", schema=SCHEMA)

    # Drop hlss_types table
    op.drop_index("idx_hlss_types_type_id", table_name="hlss_types", schema=SCHEMA)
    op.drop_table("hlss_types", schema=SCHEMA)
