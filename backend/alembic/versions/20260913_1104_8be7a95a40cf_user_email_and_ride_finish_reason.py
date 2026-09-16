"""user email and ride finish reason

Revision ID: 8be7a95a40cf
Revises: 97a553e99970
Create Date: 2026-09-13 11:04:26.185424

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "8be7a95a40cf"
down_revision: str | Sequence[str] | None = "97a553e99970"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the schema change."""
    finish_reason = postgresql.ENUM("user", "battery", name="finish_reason")
    finish_reason.create(op.get_bind(), checkfirst=True)
    op.add_column("rides", sa.Column("finish_reason", finish_reason, nullable=True))
    op.add_column("rides", sa.Column("finish_battery", sa.SmallInteger(), nullable=True))
    op.add_column("rides", sa.Column("finish_battery_threshold", sa.SmallInteger(), nullable=True))
    # every ride finished so far was finished by its rider
    op.execute("UPDATE rides SET finish_reason = 'user' WHERE status = 'finished'")
    op.add_column("users", sa.Column("email", sa.String(length=254), nullable=True))


def downgrade() -> None:
    """Revert the schema change."""
    op.drop_column("users", "email")
    op.drop_column("rides", "finish_battery_threshold")
    op.drop_column("rides", "finish_battery")
    op.drop_column("rides", "finish_reason")
    postgresql.ENUM(name="finish_reason").drop(op.get_bind(), checkfirst=True)
