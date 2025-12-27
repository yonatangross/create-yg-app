"""Memory storage and retrieval service using PostgreSQL + pgvector."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.memory import AgentMemory, ConversationSummary, MemoryType
from app.db.session import set_statement_timeout
from app.shared.services.memory.agent_memory_mapping import get_memory_types_for_agent
from app.shared.services.memory.embedding_service import (
    EmbeddingService,
    get_embedding_service,
)

logger = get_logger(__name__)


def calculate_recency_factor(last_accessed: datetime | None) -> float:
    """Calculate recency boost factor for memory ranking.

    Memories decay in relevance over time. This function returns a multiplier
    between 0.5 and 1.0 based on how recently the memory was accessed.

    Args:
        last_accessed: When the memory was last accessed (None means never).

    Returns:
        Float between 0.5 (very old) and 1.0 (recent/never accessed).
        Never-accessed memories get 1.0 to ensure they're not penalized.

    Examples:
        >>> calculate_recency_factor(None)
        1.0

        >>> calculate_recency_factor(datetime.now(UTC))
        1.0

        >>> old_date = datetime.now(UTC) - timedelta(days=365)
        >>> calculate_recency_factor(old_date)
        0.5
    """
    if last_accessed is None:
        return 1.0

    days_old = (datetime.now(UTC) - last_accessed).days

    # Linear decay: 1.0 at day 0, 0.5 at day 365
    # Capped at minimum 0.5 to avoid completely discarding old memories
    return max(0.5, 1.0 - (days_old / 365) * 0.5)


@dataclass
class MemorySearchResult:
    """Result from semantic memory search.

    Attributes:
        memory: The matched AgentMemory record.
        similarity: Cosine similarity score (0-1, higher is more similar).
        adjusted_score: Final score combining similarity, relevance, and recency.
    """

    memory: AgentMemory
    similarity: float
    adjusted_score: float


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

    def _build_contextual_text(
        self, content: str, memory_type: MemoryType | None = None
    ) -> str:
        """Build contextual text for embedding generation.

        Prepends type-specific context to improve semantic similarity.
        Based on Anthropic's Contextual Retrieval research (35% improvement).

        Args:
            content: The text content to embed.
            memory_type: Optional memory type for context prefix.

        Returns:
            Content with contextual prefix.
        """
        context_prefixes = {
            MemoryType.CONVERSATION_SUMMARY: "Summary of past conversation:",
            MemoryType.USER_PREFERENCE: "User preference or personal information:",
            MemoryType.LEARNED_FACT: "Fact learned from the user:",
            MemoryType.KEY_INSIGHT: "Key insight or important realization:",
        }

        if memory_type and memory_type in context_prefixes:
            return f"{context_prefixes[memory_type]}\n\n{content}"
        return content

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

        # Generate embedding with contextual prefix for better semantic similarity
        contextual_text = self._build_contextual_text(content, memory_type)
        embedding = await self.embedding_service.generate_embedding(contextual_text)

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
        agent_type: str | None = None,
    ) -> list[MemorySearchResult]:
        """Search memories by semantic similarity with relevance decay.

        Uses pgvector's cosine distance for similarity ranking, combined with
        relevance score and recency factor for optimized results.

        Args:
            query: Search query text.
            memory_type: Optional filter by memory type.
            conversation_id: Optional filter by conversation.
            limit: Maximum results to return.
            threshold: Minimum similarity score (0-1).
            agent_type: Optional agent type for filtering relevant memory types.

        Returns:
            List of MemorySearchResult sorted by adjusted_score (descending).
        """
        logger.debug(
            "searching_memories",
            query_length=len(query),
            memory_type=memory_type.value if memory_type else None,
            threshold=threshold,
            limit=limit,
            agent_type=agent_type,
        )

        # Set query timeout for vector search (critical query)
        await set_statement_timeout(self.session, settings.DATABASE_QUERY_TIMEOUT)

        # Generate query embedding with contextual prefix if memory_type specified
        contextual_query = self._build_contextual_text(query, memory_type)
        query_embedding = await self.embedding_service.generate_embedding(contextual_query)
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
            .limit(limit * 2)  # Fetch more for post-filtering/re-ranking
        )

        # Apply optional filters
        if memory_type:
            stmt = stmt.where(AgentMemory.memory_type == memory_type)
        if conversation_id:
            stmt = stmt.where(AgentMemory.conversation_id == conversation_id)

        # Apply agent-specific memory type filtering
        if agent_type:
            allowed_types = get_memory_types_for_agent(agent_type)
            if allowed_types:  # None means all types allowed
                stmt = stmt.where(AgentMemory.memory_type.in_(allowed_types))

        result = await self.session.execute(stmt)
        rows = result.all()

        # Calculate adjusted scores with relevance decay
        results = []
        for row in rows:
            similarity = 1.0 - row.distance
            recency = calculate_recency_factor(row.AgentMemory.last_accessed_at)
            adjusted_score = similarity * row.AgentMemory.relevance_score * recency

            results.append(
                MemorySearchResult(
                    memory=row.AgentMemory,
                    similarity=similarity,
                    adjusted_score=adjusted_score,
                )
            )

        # Sort by adjusted score and limit
        results.sort(key=lambda x: x.adjusted_score, reverse=True)
        results = results[:limit]

        logger.debug(
            "search_complete",
            results_count=len(results),
            top_similarity=results[0].similarity if results else None,
            top_adjusted_score=results[0].adjusted_score if results else None,
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

        # Track access and boost relevance for retrieved memories
        memory_ids = [r.memory.id for r in results]
        await self._track_memory_access(memory_ids)

        lines = ["## Relevant Context from Memory\n"]
        for i, r in enumerate(results, 1):
            type_label = r.memory.memory_type.replace("_", " ").title()
            lines.append(f"{i}. [{type_label}] {r.memory.content}\n")

        context_str = "\n".join(lines)

        logger.info(
            "proactive_recall_success",
            memories_found=len(results),
            context_length=len(context_str),
        )

        return context_str

    async def proactive_recall_for_agent(
        self,
        context: str,
        agent_type: str,
        limit: int = 3,
        threshold: float = 0.65,
    ) -> str:
        """Fetch relevant memories for a specific agent type.

        Like proactive_recall, but filters memories by agent type for efficiency.

        Args:
            context: Current conversation context (typically user message).
            agent_type: Agent identifier (e.g., "chat", "code_review").
            limit: Maximum memories to include.
            threshold: Minimum similarity for inclusion.

        Returns:
            Formatted context string, or empty string if no matches.
        """
        results = await self.search(
            context,
            limit=limit,
            threshold=threshold,
            agent_type=agent_type,
        )

        if not results:
            logger.debug(
                "proactive_recall_empty",
                context_length=len(context),
                agent_type=agent_type,
            )
            return ""

        # Track access and boost relevance for retrieved memories
        memory_ids = [r.memory.id for r in results]
        await self._track_memory_access(memory_ids)

        lines = ["## Relevant Context from Memory\n"]
        for i, r in enumerate(results, 1):
            type_label = r.memory.memory_type.replace("_", " ").title()
            lines.append(f"{i}. [{type_label}] {r.memory.content}\n")

        context_str = "\n".join(lines)

        logger.info(
            "proactive_recall_success",
            agent_type=agent_type,
            memories_found=len(results),
            context_length=len(context_str),
        )

        return context_str

    async def _track_memory_access(self, memory_ids: list[UUID]) -> None:
        """Update last_accessed_at and boost relevance for accessed memories.

        Performs a single batched UPDATE for all memory IDs using SQL LEAST function
        to cap relevance at 1.0. This avoids N+1 queries.

        Args:
            memory_ids: List of memory IDs that were accessed.
        """
        if not memory_ids:
            return

        from sqlalchemy import func

        # Single UPDATE for all IDs with proper relevance capping
        # LEAST ensures relevance never exceeds 1.0
        stmt = (
            update(AgentMemory)
            .where(AgentMemory.id.in_(memory_ids))
            .values(
                last_accessed_at=func.now(),
                relevance_score=func.least(AgentMemory.relevance_score + 0.1, 1.0),
            )
        )

        await self.session.execute(stmt)
        await self.session.commit()

        logger.debug("memory_access_tracked", count=len(memory_ids))

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
