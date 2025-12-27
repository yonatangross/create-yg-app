"""Add memory tables for semantic storage.

Revision ID: 20251227_0001
Revises: None
Create Date: 2025-12-27

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "20251227_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create memory tables with pgvector support."""
    # Ensure pgvector extension exists
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create agent_memories table
    op.create_table(
        "agent_memories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("memory_type", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("conversation_id", sa.String(length=100), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True, default=1.0),
        sa.Column("memory_metadata", sa.JSON(), nullable=True, default={}),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for agent_memories
    op.create_index(
        "ix_agent_memories_memory_type",
        "agent_memories",
        ["memory_type"],
        unique=False,
    )
    op.create_index(
        "ix_agent_memories_conversation_id",
        "agent_memories",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_agent_memories_type_created",
        "agent_memories",
        ["memory_type", "created_at"],
        unique=False,
    )

    # Create HNSW index for vector similarity search
    op.execute(
        """
        CREATE INDEX ix_agent_memories_embedding_hnsw
        ON agent_memories
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # Create conversation_summaries table
    op.create_table(
        "conversation_summaries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.String(length=100), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=True, default=0),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id"),
    )

    # Create index for conversation_summaries
    op.create_index(
        "ix_conversation_summaries_conversation_id",
        "conversation_summaries",
        ["conversation_id"],
        unique=True,
    )


def downgrade() -> None:
    """Remove memory tables."""
    op.drop_index("ix_conversation_summaries_conversation_id", "conversation_summaries")
    op.drop_table("conversation_summaries")

    op.execute("DROP INDEX IF EXISTS ix_agent_memories_embedding_hnsw")
    op.drop_index("ix_agent_memories_type_created", "agent_memories")
    op.drop_index("ix_agent_memories_conversation_id", "agent_memories")
    op.drop_index("ix_agent_memories_memory_type", "agent_memories")
    op.drop_table("agent_memories")
