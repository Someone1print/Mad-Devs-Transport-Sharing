"""create bookings

Revision ID: 2adf55bceaa7
Revises: 090661a2ea44
Create Date: 2026-09-10 18:56:06.504258

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2adf55bceaa7"
down_revision: str | Sequence[str] | None = "090661a2ea44"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the schema change."""
    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("scooter_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "cancelled", "expired", name="booking_status"),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("warned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["scooter_id"], ["scooters.id"], name=op.f("fk_bookings_scooter_id_scooters")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_bookings_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bookings")),
    )
    op.create_index(
        "uq_bookings_active_scooter",
        "bookings",
        ["scooter_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "uq_bookings_active_user",
        "bookings",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    """Revert the schema change."""
    op.drop_index(
        "uq_bookings_active_user",
        table_name="bookings",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_index(
        "uq_bookings_active_scooter",
        table_name="bookings",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_table("bookings")
