"""conversations: user_id + title for signed-in chat history

Revision ID: a1b2c3d4e5f6
Revises: f97959c1101d
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f97959c1101d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column("conversations", sa.Column("title", sa.String(length=160), nullable=True))
    op.create_index(op.f("ix_conversations_user_id"), "conversations", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_conversations_user_id"), table_name="conversations")
    op.drop_column("conversations", "title")
    op.drop_column("conversations", "user_id")
