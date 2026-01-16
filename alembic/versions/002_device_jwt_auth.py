"""
Device JWT authentication schema changes

Revision ID: 002_device_jwt_auth
Revises: 001_add_hlss_admin
Create Date: 2026-01-16

This migration adds JWT-based authentication support for devices:
- Removes access_token column (replaced by JWT)
- Adds auth_status for device authorization workflow
- Adds authorized_at and authorized_by for audit
- Adds current_refresh_jti for token revocation
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "002_device_jwt_auth"
down_revision = "001_add_hlss_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns for JWT auth
    op.add_column(
        "devices",
        sa.Column(
            "auth_status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        schema="eink",
    )
    op.add_column(
        "devices",
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        schema="eink",
    )
    op.add_column(
        "devices",
        sa.Column("authorized_by", sa.String(100), nullable=True),
        schema="eink",
    )
    op.add_column(
        "devices",
        sa.Column("current_refresh_jti", sa.String(64), nullable=True),
        schema="eink",
    )

    # Create index on auth_status for filtering pending devices
    op.create_index(
        "ix_devices_auth_status",
        "devices",
        ["auth_status"],
        schema="eink",
    )

    # Migrate existing devices to authorized status
    # (they have access_tokens so they were previously working)
    op.execute(
        """
        UPDATE eink.devices 
        SET auth_status = 'authorized', 
            authorized_at = created_at
        WHERE access_token IS NOT NULL AND access_token != ''
        """
    )

    # Now we can drop the access_token column
    # First drop the index if it exists
    op.drop_index("ix_devices_access_token", table_name="devices", schema="eink")
    op.drop_column("devices", "access_token", schema="eink")


def downgrade() -> None:
    # Re-add access_token column
    op.add_column(
        "devices",
        sa.Column("access_token", sa.String(64), nullable=True),
        schema="eink",
    )
    op.create_index(
        "ix_devices_access_token",
        "devices",
        ["access_token"],
        schema="eink",
    )

    # Generate access tokens for authorized devices
    # Note: This won't restore the original tokens!
    op.execute(
        """
        UPDATE eink.devices 
        SET access_token = encode(gen_random_bytes(32), 'base64')
        WHERE auth_status = 'authorized'
        """
    )

    # Make access_token non-nullable after populating
    op.alter_column(
        "devices",
        "access_token",
        nullable=False,
        schema="eink",
    )

    # Remove JWT auth columns
    op.drop_index("ix_devices_auth_status", table_name="devices", schema="eink")
    op.drop_column("devices", "current_refresh_jti", schema="eink")
    op.drop_column("devices", "authorized_by", schema="eink")
    op.drop_column("devices", "authorized_at", schema="eink")
    op.drop_column("devices", "auth_status", schema="eink")
