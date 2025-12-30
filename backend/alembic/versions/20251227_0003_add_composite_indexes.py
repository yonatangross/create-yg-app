"""Add composite indexes for query optimization.

Revision ID: 20251227_0003
Revises: 20251227_0002
Create Date: 2025-12-27

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20251227_0003"
down_revision: str | None = "20251227_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add composite indexes for optimized memory queries."""
    # Composite index for memory type + conversation queries
    # Using raw SQL with IF NOT EXISTS for idempotency
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_agent_memories_type_conv
        ON agent_memories (memory_type, conversation_id)
        WHERE conversation_id IS NOT NULL
        """
    )

    # Index for recently accessed memories (sorted by last_accessed_at DESC)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_agent_memories_last_accessed
        ON agent_memories (last_accessed_at)
        """
    )


def downgrade() -> None:
    """Remove composite indexes."""
    op.execute("DROP INDEX IF EXISTS ix_agent_memories_last_accessed")
    op.execute("DROP INDEX IF EXISTS ix_agent_memories_type_conv")
