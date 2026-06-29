"""
Per-band enabled-slot bitmask on Frame

Revision ID: 005_enabled_mask
Revises: 004_pressed_strips
Create Date: 2026-06-29

Adds frames.top_enabled_mask and frames.bottom_enabled_mask. Each is an
8-bit-meaningful integer (bit S = slot S is pressable). The device reads
them from /state and /inputs to gate local press-feedback so an empty or
otherwise-disabled slot does not flash.
"""

from alembic import op
import sqlalchemy as sa


revision = "005_enabled_mask"
down_revision = "004_pressed_strips"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "frames",
        sa.Column("top_enabled_mask", sa.Integer(), nullable=True),
        schema="eink_llss",
    )
    op.add_column(
        "frames",
        sa.Column("bottom_enabled_mask", sa.Integer(), nullable=True),
        schema="eink_llss",
    )


def downgrade() -> None:
    op.drop_column("frames", "bottom_enabled_mask", schema="eink_llss")
    op.drop_column("frames", "top_enabled_mask", schema="eink_llss")
