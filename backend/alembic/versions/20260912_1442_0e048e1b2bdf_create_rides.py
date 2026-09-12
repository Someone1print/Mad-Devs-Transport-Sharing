"""create rides, ride_segments and service_zones

Revision ID: 0e048e1b2bdf
Revises: 2adf55bceaa7
Create Date: 2026-09-12 14:42:32.708173

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0e048e1b2bdf"
down_revision: str | Sequence[str] | None = "2adf55bceaa7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RIDE_STATUS = sa.Enum("active", "paused", "finished", name="ride_status")
SEGMENT_KIND = sa.Enum("ride", "pause", name="segment_kind")


def upgrade() -> None:
    """Apply the schema change."""
    # A booking converted into a ride is 'used'. Alembic does not diff enum members, and on
    # PostgreSQL 16 ADD VALUE may run inside the migration transaction as long as the new value
    # is not used in the same transaction.
    op.execute("ALTER TYPE booking_status ADD VALUE IF NOT EXISTS 'used'")

    op.add_column(
        "scooters",
        sa.Column("paused", sa.Boolean(), server_default=sa.false(), nullable=False),
    )

    op.create_table(
        "service_zones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("points", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_zones")),
        sa.UniqueConstraint("name", name=op.f("uq_service_zones_name")),
    )
    op.create_table(
        "rides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("scooter_id", sa.Integer(), nullable=False),
        sa.Column("booking_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "paused", "finished", name="ride_status"),
            server_default="active",
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ride_rate_per_minute", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("pause_rate_per_minute", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("ride_seconds", sa.Integer(), nullable=True),
        sa.Column("pause_seconds", sa.Integer(), nullable=True),
        sa.Column("ride_cost", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("pause_cost", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("total_cost", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "total_cost = ride_cost + pause_cost", name=op.f("ck_rides_receipt_adds_up")
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"], ["bookings.id"], name=op.f("fk_rides_booking_id_bookings")
        ),
        sa.ForeignKeyConstraint(
            ["scooter_id"], ["scooters.id"], name=op.f("fk_rides_scooter_id_scooters")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_rides_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rides")),
        sa.UniqueConstraint("booking_id", name=op.f("uq_rides_booking_id")),
    )
    op.create_index(
        "uq_rides_unfinished_scooter",
        "rides",
        ["scooter_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'finished'"),
    )
    op.create_index(
        "uq_rides_unfinished_user",
        "rides",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'finished'"),
    )
    op.create_table(
        "ride_segments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ride_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Enum("ride", "pause", name="segment_kind"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seconds", sa.Integer(), nullable=True),
        sa.Column("cost", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.ForeignKeyConstraint(
            ["ride_id"],
            ["rides.id"],
            name=op.f("fk_ride_segments_ride_id_rides"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ride_segments")),
    )
    op.create_index(op.f("ix_ride_segments_ride_id"), "ride_segments", ["ride_id"], unique=False)


def downgrade() -> None:
    """Revert the schema change."""
    op.drop_index(op.f("ix_ride_segments_ride_id"), table_name="ride_segments")
    op.drop_table("ride_segments")
    op.drop_index(
        "uq_rides_unfinished_user",
        table_name="rides",
        postgresql_where=sa.text("status <> 'finished'"),
    )
    op.drop_index(
        "uq_rides_unfinished_scooter",
        table_name="rides",
        postgresql_where=sa.text("status <> 'finished'"),
    )
    op.drop_table("rides")
    RIDE_STATUS.drop(op.get_bind(), checkfirst=False)
    SEGMENT_KIND.drop(op.get_bind(), checkfirst=False)
    op.drop_table("service_zones")
    op.drop_column("scooters", "paused")

    # PostgreSQL cannot remove an enum value: rebuild booking_status without 'used'.
    # Bookings that were converted into rides are recorded as expired afterwards.
    # The partial unique indexes reference the enum in their predicate, so they must be
    # rebuilt around the type swap.
    op.execute("UPDATE bookings SET status = 'expired' WHERE status = 'used'")
    op.execute("DROP INDEX uq_bookings_active_scooter")
    op.execute("DROP INDEX uq_bookings_active_user")
    op.execute("ALTER TABLE bookings ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TYPE booking_status RENAME TO booking_status_old")
    op.execute("CREATE TYPE booking_status AS ENUM ('active', 'cancelled', 'expired')")
    op.execute(
        "ALTER TABLE bookings ALTER COLUMN status TYPE booking_status "
        "USING status::text::booking_status"
    )
    op.execute("ALTER TABLE bookings ALTER COLUMN status SET DEFAULT 'active'")
    op.execute("DROP TYPE booking_status_old")
    op.execute(
        "CREATE UNIQUE INDEX uq_bookings_active_scooter ON bookings (scooter_id) "
        "WHERE status = 'active'"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_bookings_active_user ON bookings (user_id) WHERE status = 'active'"
    )
