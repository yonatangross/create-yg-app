"""Add tsvector column for hybrid BM25+vector search.

Revision ID: 20251227_0004
Revises: 20251227_0003
Create Date: 2025-12-27

This migration adds:
1. content_tsvector column (generated from content)
2. GIN index for fast full-text search

Together with the existing HNSW vector index, this enables
hybrid search using Reciprocal Rank Fusion (RRF).
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20251227_0004"
down_revision = "20251227_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add tsvector column and GIN index for hybrid search."""
    # Add generated tsvector column for full-text search
    # GENERATED ALWAYS means it auto-updates when content changes
    op.execute("""
        ALTER TABLE agent_memories
        ADD COLUMN content_tsvector tsvector
        GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
    """)

    # Create GIN index for fast full-text search
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_agent_memories_content_tsvector
        ON agent_memories USING gin (content_tsvector)
    """)


def downgrade() -> None:
    """Remove tsvector column and GIN index."""
    op.execute("DROP INDEX IF EXISTS ix_agent_memories_content_tsvector")
    op.execute("ALTER TABLE agent_memories DROP COLUMN IF EXISTS content_tsvector")
