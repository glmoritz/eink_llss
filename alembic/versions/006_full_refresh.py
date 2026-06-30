"""
Frame full-refresh hint

Revision ID: 006_full_refresh
Revises: 005_enabled_mask
Create Date: 2026-06-30

Adds frames.full_refresh. HLSS sets it for view-mode toggles and any
frame where the board position actually changed; the device honours
the hint by driving a full e-ink refresh (UI_CTX_SWITCH) instead of
partial. Defaults to false so the partial path stays the steady state.
"""

from alembic import op
import sqlalchemy as sa


revision = "006_full_refresh"
down_revision = "005_enabled_mask"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "frames",
        sa.Column(
            "full_refresh",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema="eink_llss",
    )


def downgrade() -> None:
    op.drop_column("frames", "full_refresh", schema="eink_llss")
