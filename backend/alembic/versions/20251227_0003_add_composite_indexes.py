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
    # Useful for: SELECT * FROM agent_memories WHERE memory_type = ? AND conversation_id = ?
    op.create_index(
        "ix_agent_memories_type_conv",
        "agent_memories",
        ["memory_type", "conversation_id"],
        postgresql_where="conversation_id IS NOT NULL",
        unique=False,
    )

    # Partial index for active memories (accessed recently)
    # Useful for: SELECT * FROM agent_memories WHERE last_accessed_at > NOW() - INTERVAL '30 days'
    op.execute(
        """
        CREATE INDEX ix_agent_memories_active
        ON agent_memories (last_accessed_at)
        WHERE last_accessed_at > NOW() - INTERVAL '30 days'
        """
    )


def downgrade() -> None:
    """Remove composite indexes."""
    op.drop_index("ix_agent_memories_active", "agent_memories")
    op.drop_index("ix_agent_memories_type_conv", "agent_memories")
