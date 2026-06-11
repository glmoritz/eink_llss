"""
Expand instance access_token to support JWT

Revision ID: 003_instance_access_token_jwt
Revises: 002_device_jwt_auth
Create Date: 2026-01-16

This migration expands the instances.access_token column to TEXT to
support JWTs signed with the HLSS shared key.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "003_instance_access_token_jwt"
down_revision = "002_device_jwt_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop index on access_token (JWTs are long and no longer used for lookup)
    op.drop_index("ix_instances_access_token", table_name="instances", schema="eink")

    # Expand column to TEXT for JWT storage
    op.alter_column(
        "instances",
        "access_token",
        type_=sa.Text(),
        existing_type=sa.String(length=64),
        nullable=True,
        schema="eink",
    )


def downgrade() -> None:
    # Revert column to VARCHAR(64)
    op.alter_column(
        "instances",
        "access_token",
        type_=sa.String(length=64),
        existing_type=sa.Text(),
        nullable=True,
        schema="eink",
    )

    # Recreate index for legacy lookup
    op.create_index(
        "ix_instances_access_token",
        "instances",
        ["access_token"],
        schema="eink",
    )
