"""user password hash and sessions

Revision ID: 5c1a9e7d2b40
Revises: 8be7a95a40cf
Create Date: 2026-09-17 19:11:31.366238

Accounts get a password (argon2 hash) and a table of sessions. Existing rows keep
`password_hash = NULL`: they are legacy accounts that registration can claim (see
app/services/auth.py), so nobody loses rides or history with the upgrade. The e-mail is unique
only among accounts with a password — legacy rows may repeat an address and must not block
the migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5c1a9e7d2b40"
down_revision: str | Sequence[str] | None = "8be7a95a40cf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the schema change."""
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_user_sessions_token_hash")),
    )
    op.create_index(op.f("ix_user_sessions_user_id"), "user_sessions", ["user_id"], unique=False)
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    # one registered account per address (case-insensitive); legacy rows are exempt
    op.execute(
        "CREATE UNIQUE INDEX uq_users_email_registered ON users (lower(email)) "
        "WHERE password_hash IS NOT NULL"
    )


def downgrade() -> None:
    """Revert the schema change."""
    op.execute("DROP INDEX uq_users_email_registered")
    op.drop_column("users", "password_hash")
    op.drop_index(op.f("ix_user_sessions_user_id"), table_name="user_sessions")
    op.drop_table("user_sessions")
