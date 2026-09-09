"""create scooters

Revision ID: 3461bebe962e
Revises:
Create Date: 2026-09-09 19:21:36.870187

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3461bebe962e"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOOTER_STATUS = sa.Enum("available", "reserved", "riding", "unavailable", name="scooter_status")


def upgrade() -> None:
    """Create the scooters table and the scooter_status enum type."""
    op.create_table(
        "scooters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("lat", sa.Double(), nullable=False),
        sa.Column("lon", sa.Double(), nullable=False),
        sa.Column("battery", sa.SmallInteger(), nullable=False),
        sa.Column("status", SCOOTER_STATUS, server_default="available", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint("battery BETWEEN 0 AND 100", name=op.f("ck_scooters_battery_range")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scooters")),
        sa.UniqueConstraint("code", name=op.f("uq_scooters_code")),
    )


def downgrade() -> None:
    """Drop the scooters table and the enum type it owns."""
    op.drop_table("scooters")
    SCOOTER_STATUS.drop(op.get_bind(), checkfirst=False)
