"""Add last_accessed_at column to agent_memories for relevance decay.

Revision ID: 20251227_0002
Revises: 20251227_0001
Create Date: 2025-12-27

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20251227_0002"
down_revision: str | None = "20251227_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add last_accessed_at column to agent_memories table."""
    op.add_column(
        "agent_memories",
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create index for queries that sort by last_accessed_at
    op.create_index(
        "ix_agent_memories_last_accessed",
        "agent_memories",
        ["last_accessed_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove last_accessed_at column from agent_memories table."""
    op.drop_index("ix_agent_memories_last_accessed", "agent_memories")
    op.drop_column("agent_memories", "last_accessed_at")
