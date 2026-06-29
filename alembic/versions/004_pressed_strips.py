"""
Pressed-state strips: content-addressed strip storage + frame references

Revision ID: 004_pressed_strips
Revises: 003_instance_access_token_jwt
Create Date: 2026-06-29

Adds:
  - `strips` table: content-hash-keyed pressed-state button strips uploaded
    by HLSS alongside each frame. One row per unique content; multiple
    frames can reference the same strip id (visually-identical buttons
    across frames).
  - `frames.top_strip_id` / `frames.bottom_strip_id`: optional references
    to the strip rows associated with each frame. Returned to the device
    in DeviceStateResponse / InputProcessResponse.
"""

from alembic import op
import sqlalchemy as sa


revision = "004_pressed_strips"
down_revision = "003_instance_access_token_jwt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strips",
        sa.Column("strip_id", sa.String(length=32), primary_key=True),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        schema="eink",
    )

    op.add_column(
        "frames",
        sa.Column("top_strip_id", sa.String(length=32), nullable=True),
        schema="eink",
    )
    op.add_column(
        "frames",
        sa.Column("bottom_strip_id", sa.String(length=32), nullable=True),
        schema="eink",
    )
    op.create_index(
        "ix_frames_top_strip_id",
        "frames",
        ["top_strip_id"],
        schema="eink",
    )
    op.create_index(
        "ix_frames_bottom_strip_id",
        "frames",
        ["bottom_strip_id"],
        schema="eink",
    )


def downgrade() -> None:
    op.drop_index("ix_frames_bottom_strip_id", table_name="frames", schema="eink")
    op.drop_index("ix_frames_top_strip_id", table_name="frames", schema="eink")
    op.drop_column("frames", "bottom_strip_id", schema="eink")
    op.drop_column("frames", "top_strip_id", schema="eink")
    op.drop_table("strips", schema="eink")
