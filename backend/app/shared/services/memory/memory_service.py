"""Memory storage and retrieval service using PostgreSQL + pgvector."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.memory import AgentMemory, ConversationSummary, MemoryType
from app.shared.services.memory.embedding_service import (
    EmbeddingService,
    get_embedding_service,
)

logger = get_logger(__name__)


@dataclass
class MemorySearchResult:
    """Result from semantic memory search.

    Attributes:
        memory: The matched AgentMemory record.
        similarity: Cosine similarity score (0-1, higher is more similar).
    """

    memory: AgentMemory
    similarity: float


class MemoryService:
    """Store and retrieve semantic memories using pgvector.

    Provides:
    - store(): Persist memory with auto-generated embedding
    - search(): Semantic similarity search
    - proactive_recall(): Context injection for agent prompts

    Example:
        async with get_session() as session:
            service = MemoryService(session)
            await service.store("User prefers dark mode", MemoryType.USER_PREFERENCE)
            results = await service.search("theme preferences", limit=3)
    """

    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        """Initialize memory service.

        Args:
            session: Async SQLAlchemy session for database operations.
            embedding_service: Optional custom embedding service.
        """
        self.session = session
        self.embedding_service = embedding_service or get_embedding_service()

    async def store(
        self,
        content: str,
        memory_type: MemoryType,
        conversation_id: str | None = None,
        metadata: dict | None = None,
        relevance_score: float = 1.0,
    ) -> AgentMemory:
        """Store a memory with its embedding vector.

        Args:
            content: The text content to store.
            memory_type: Classification of the memory.
            conversation_id: Optional conversation association.
            metadata: Optional additional metadata.
            relevance_score: Initial relevance (0-1).

        Returns:
            The created AgentMemory record.
        """
        logger.debug(
            "storing_memory",
            memory_type=memory_type.value,
            content_length=len(content),
            conversation_id=conversation_id,
        )

        # Generate embedding
        embedding = await self.embedding_service.generate_embedding(content)

        # Create memory record
        memory = AgentMemory(
            memory_type=memory_type,
            content=content,
            embedding=embedding,
            conversation_id=conversation_id,
            relevance_score=relevance_score,
            memory_metadata=metadata or {},
        )

        self.session.add(memory)
        await self.session.commit()
        await self.session.refresh(memory)

        logger.info(
            "memory_stored",
            memory_id=str(memory.id),
            memory_type=memory_type.value,
        )

        return memory

    async def search(
        self,
        query: str,
        memory_type: MemoryType | None = None,
        conversation_id: str | None = None,
        limit: int = 5,
        threshold: float = 0.7,
    ) -> list[MemorySearchResult]:
        """Search memories by semantic similarity.

        Uses pgvector's cosine distance for similarity ranking.
        Distance = 1 - similarity, so we filter by distance <= (1 - threshold).

        Args:
            query: Search query text.
            memory_type: Optional filter by memory type.
            conversation_id: Optional filter by conversation.
            limit: Maximum results to return.
            threshold: Minimum similarity score (0-1).

        Returns:
            List of MemorySearchResult sorted by similarity (descending).
        """
        logger.debug(
            "searching_memories",
            query_length=len(query),
            memory_type=memory_type.value if memory_type else None,
            threshold=threshold,
            limit=limit,
        )

        # Generate query embedding
        query_embedding = await self.embedding_service.generate_embedding(query)
        max_distance = 1.0 - threshold

        # Build query with cosine distance
        # pgvector: smaller distance = more similar
        stmt = (
            select(
                AgentMemory,
                AgentMemory.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .where(AgentMemory.embedding.cosine_distance(query_embedding) <= max_distance)
            .order_by("distance")
            .limit(limit)
        )

        # Apply optional filters
        if memory_type:
            stmt = stmt.where(AgentMemory.memory_type == memory_type)
        if conversation_id:
            stmt = stmt.where(AgentMemory.conversation_id == conversation_id)

        result = await self.session.execute(stmt)
        rows = result.all()

        results = [
            MemorySearchResult(
                memory=row.AgentMemory,
                similarity=1.0 - row.distance,
            )
            for row in rows
        ]

        logger.debug(
            "search_complete",
            results_count=len(results),
            top_similarity=results[0].similarity if results else None,
        )

        return results

    async def proactive_recall(
        self,
        context: str,
        limit: int = 3,
        threshold: float = 0.65,
    ) -> str:
        """Fetch relevant memories for context injection.

        Generates a formatted string suitable for prepending to system prompts.

        Args:
            context: Current conversation context (typically user message).
            limit: Maximum memories to include.
            threshold: Minimum similarity for inclusion.

        Returns:
            Formatted context string, or empty string if no matches.
        """
        results = await self.search(context, limit=limit, threshold=threshold)

        if not results:
            logger.debug("proactive_recall_empty", context_length=len(context))
            return ""

        lines = ["## Relevant Context from Memory\n"]
        for i, r in enumerate(results, 1):
            type_label = r.memory.memory_type.value.replace("_", " ").title()
            lines.append(f"{i}. [{type_label}] {r.memory.content}\n")

        context_str = "\n".join(lines)

        logger.info(
            "proactive_recall_success",
            memories_found=len(results),
            context_length=len(context_str),
        )

        return context_str

    async def get_conversation_summary(
        self,
        conversation_id: str,
    ) -> ConversationSummary | None:
        """Get existing summary for a conversation.

        Args:
            conversation_id: The conversation to look up.

        Returns:
            ConversationSummary if exists, None otherwise.
        """
        stmt = select(ConversationSummary).where(
            ConversationSummary.conversation_id == conversation_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_conversation_summary(
        self,
        conversation_id: str,
        summary: str,
        message_count: int,
    ) -> ConversationSummary:
        """Save or update a conversation summary.

        Also stores the summary as a long-term memory with embedding.

        Args:
            conversation_id: The conversation being summarized.
            summary: The compressed summary text.
            message_count: Number of messages summarized.

        Returns:
            The created or updated ConversationSummary.
        """
        from datetime import UTC, datetime

        existing = await self.get_conversation_summary(conversation_id)

        if existing:
            existing.summary = summary
            existing.message_count = message_count
            existing.updated_at = datetime.now(UTC)
            await self.session.commit()
            await self.session.refresh(existing)
            record = existing
        else:
            record = ConversationSummary(
                conversation_id=conversation_id,
                summary=summary,
                message_count=message_count,
                last_message_at=datetime.now(UTC),
            )
            self.session.add(record)
            await self.session.commit()
            await self.session.refresh(record)

        # Also store as searchable memory
        await self.store(
            content=summary,
            memory_type=MemoryType.CONVERSATION_SUMMARY,
            conversation_id=conversation_id,
            metadata={"message_count": message_count},
        )

        logger.info(
            "conversation_summary_saved",
            conversation_id=conversation_id,
            message_count=message_count,
        )

        return record

    async def delete_memory(self, memory_id: UUID) -> bool:
        """Delete a specific memory by ID.

        Args:
            memory_id: The memory UUID to delete.

        Returns:
            True if deleted, False if not found.
        """
        stmt = select(AgentMemory).where(AgentMemory.id == memory_id)
        result = await self.session.execute(stmt)
        memory = result.scalar_one_or_none()

        if memory:
            await self.session.delete(memory)
            await self.session.commit()
            logger.info("memory_deleted", memory_id=str(memory_id))
            return True

        return False

    async def get_memories_by_type(
        self,
        memory_type: MemoryType,
        limit: int = 50,
    ) -> list[AgentMemory]:
        """Get all memories of a specific type.

        Args:
            memory_type: The type to filter by.
            limit: Maximum records to return.

        Returns:
            List of AgentMemory records.
        """
        stmt = (
            select(AgentMemory)
            .where(AgentMemory.memory_type == memory_type)
            .order_by(AgentMemory.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
