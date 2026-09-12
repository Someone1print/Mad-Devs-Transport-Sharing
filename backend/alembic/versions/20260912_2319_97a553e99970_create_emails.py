"""create emails

Revision ID: 97a553e99970
Revises: 0e048e1b2bdf
Create Date: 2026-09-12 23:19:00.677755

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "97a553e99970"
down_revision: str | Sequence[str] | None = "0e048e1b2bdf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the schema change."""
    op.create_table(
        "emails",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("to_address", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("dedup_key", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_emails_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_emails")),
        sa.UniqueConstraint("dedup_key", name=op.f("uq_emails_dedup_key")),
    )
    op.create_index(op.f("ix_emails_user_id"), "emails", ["user_id"], unique=False)


def downgrade() -> None:
    """Revert the schema change."""
    op.drop_index(op.f("ix_emails_user_id"), table_name="emails")
    op.drop_table("emails")
