"""Memory models for semantic storage and conversation history."""

import uuid
from datetime import datetime
from enum import Enum

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MemoryType(str, Enum):
    """Classification of memory entries."""

    CONVERSATION_SUMMARY = "conversation_summary"
    USER_PREFERENCE = "user_preference"
    LEARNED_FACT = "learned_fact"
    KEY_INSIGHT = "key_insight"


class AgentMemory(Base):
    """Semantic memory entries with vector embeddings.

    Stores memories with 1536-dimensional embeddings for semantic search
    using pgvector's cosine distance.

    Attributes:
        id: Unique identifier.
        memory_type: Classification (conversation_summary, user_preference, etc.).
        content: The actual memory content.
        embedding: 1536-dim vector from OpenAI text-embedding-3-small.
        conversation_id: Optional link to source conversation.
        relevance_score: Quality metric (0-1).
        memory_metadata: Flexible JSONB for additional context.
        created_at: Timestamp of creation.
    """

    __tablename__ = "agent_memories"

    id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Classification
    memory_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # Content and embedding
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(1536),
        nullable=False,
    )

    # Metadata
    conversation_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    relevance_score: Mapped[float] = mapped_column(
        Float,
        default=1.0,
    )
    memory_metadata: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        # HNSW index for fast approximate nearest neighbor search
        Index(
            "ix_agent_memories_embedding_hnsw",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        # Composite index for filtered queries
        Index("ix_agent_memories_type_created", memory_type, created_at),
    )

    def __repr__(self) -> str:
        return f"<AgentMemory(id={self.id}, type={self.memory_type})>"


class ConversationSummary(Base):
    """Compressed conversation history for long-term storage.

    When a conversation grows too long, it gets summarized and stored here.
    The summary can then be used as context for future conversations.

    Attributes:
        id: Unique identifier.
        conversation_id: The conversation this summarizes (unique).
        summary: Compressed text summary.
        message_count: Number of messages summarized.
        last_message_at: Timestamp of last message before summarization.
        created_at: When the summary was created.
        updated_at: When the summary was last updated.
    """

    __tablename__ = "conversation_summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    conversation_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    summary: Mapped[str] = mapped_column(Text, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<ConversationSummary(id={self.id}, conv_id={self.conversation_id})>"
