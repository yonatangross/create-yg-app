"""Memory storage and retrieval service using PostgreSQL + pgvector.

Implements hybrid search combining:
- Vector similarity search (semantic meaning via embeddings)
- BM25 keyword search (exact term matching via tsvector)
- Reciprocal Rank Fusion (RRF) for combining results

This achieves ~49% improvement over vector-only search.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
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

# RRF smoothing constant (standard value from literature)
RRF_K = 60

# Fetch multiplier for RRF (retrieve more candidates for better fusion)
RRF_FETCH_MULTIPLIER = 3

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

    def _build_contextual_text(self, content: str, memory_type: MemoryType | None = None) -> str:
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
        """Search memories using hybrid BM25 + vector search with RRF.

        Combines semantic similarity (vector embeddings) with keyword matching
        (BM25 via tsvector) using Reciprocal Rank Fusion for optimal results.
        This achieves ~49% improvement over vector-only search.

        Args:
            query: Search query text.
            memory_type: Optional filter by memory type.
            conversation_id: Optional filter by conversation.
            limit: Maximum results to return.
            threshold: Minimum similarity score (0-1).
            agent_type: Optional agent type for filtering relevant memory types.

        Returns:
            List of MemorySearchResult sorted by RRF score (descending).
        """
        logger.debug(
            "hybrid_search_start",
            query_length=len(query),
            memory_type=memory_type.value if memory_type else None,
            threshold=threshold,
            limit=limit,
            agent_type=agent_type,
        )

        # Set query timeout for search (critical query)
        await set_statement_timeout(self.session, settings.DATABASE_QUERY_TIMEOUT)

        # Generate query embedding with contextual prefix
        contextual_query = self._build_contextual_text(query, memory_type)
        query_embedding = await self.embedding_service.generate_embedding(contextual_query)

        # Fetch more candidates for RRF fusion
        fetch_limit = limit * RRF_FETCH_MULTIPLIER

        # Build base filter conditions
        filters = []
        if memory_type:
            filters.append(AgentMemory.memory_type == memory_type)
        if conversation_id:
            filters.append(AgentMemory.conversation_id == conversation_id)
        if agent_type:
            allowed_types = get_memory_types_for_agent(agent_type)
            if allowed_types:
                filters.append(AgentMemory.memory_type.in_(allowed_types))

        # ===== 1. VECTOR SEARCH =====
        # No threshold filter - we use RRF ranking instead
        vector_stmt = select(
            AgentMemory.id,
            AgentMemory.embedding.cosine_distance(query_embedding).label("distance"),
            func.row_number()
            .over(order_by=AgentMemory.embedding.cosine_distance(query_embedding))
            .label("vector_rank"),
        ).where(AgentMemory.embedding.isnot(None))
        for f in filters:
            vector_stmt = vector_stmt.where(f)
        vector_stmt = vector_stmt.limit(fetch_limit)

        # ===== 2. KEYWORD SEARCH (BM25 via tsvector) =====
        ts_query = func.plainto_tsquery("english", query)

        keyword_stmt = select(
            AgentMemory.id,
            func.ts_rank_cd(AgentMemory.content_tsvector, ts_query).label("bm25_score"),
            func.row_number()
            .over(order_by=func.ts_rank_cd(AgentMemory.content_tsvector, ts_query).desc())
            .label("keyword_rank"),
        ).where(AgentMemory.content_tsvector.op("@@")(ts_query))
        for f in filters:
            keyword_stmt = keyword_stmt.where(f)
        keyword_stmt = keyword_stmt.limit(fetch_limit)

        # ===== 3. RECIPROCAL RANK FUSION (RRF) =====
        # Combine results using RRF: score = 1/(k + rank_vector) + 1/(k + rank_keyword)
        # Fetch both result sets and merge in Python for FULL OUTER JOIN semantics
        vector_result = await self.session.execute(vector_stmt)
        vector_rows = {row.id: (row.distance, row.vector_rank) for row in vector_result}

        keyword_result = await self.session.execute(keyword_stmt)
        keyword_rows = {row.id: (row.bm25_score, row.keyword_rank) for row in keyword_result}

        # Calculate RRF scores for all candidates
        all_ids = set(vector_rows.keys()) | set(keyword_rows.keys())
        rrf_scores: dict[UUID, tuple[float, float]] = {}

        for memory_id in all_ids:
            vector_rank = vector_rows.get(memory_id, (None, None))[1]
            keyword_rank = keyword_rows.get(memory_id, (None, None))[1]

            # Calculate RRF score
            rrf = 0.0
            if vector_rank is not None:
                rrf += 1.0 / (RRF_K + vector_rank)
            if keyword_rank is not None:
                rrf += 1.0 / (RRF_K + keyword_rank)

            # Store similarity (from vector distance) for threshold filtering
            vector_distance = vector_rows.get(memory_id, (1.0, None))[0]
            similarity = 1.0 - (vector_distance if vector_distance else 1.0)

            rrf_scores[memory_id] = (rrf, similarity)

        # Sort by RRF score and apply threshold
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x][0], reverse=True)

        # Filter by similarity threshold and limit
        filtered_ids = []
        for memory_id in sorted_ids:
            rrf, similarity = rrf_scores[memory_id]
            # Apply threshold: either high similarity OR appeared in keyword search
            # This is more lenient than vector-only threshold
            if similarity >= threshold or memory_id in keyword_rows:
                filtered_ids.append(memory_id)
            if len(filtered_ids) >= limit:
                break

        if not filtered_ids:
            logger.debug("hybrid_search_empty", query_length=len(query))
            return []

        # ===== 4. FETCH FULL MEMORY RECORDS =====
        memories_stmt = select(AgentMemory).where(AgentMemory.id.in_(filtered_ids))
        memories_result = await self.session.execute(memories_stmt)
        memories_by_id = {m.id: m for m in memories_result.scalars().all()}

        # Build results with proper scoring
        results = []
        for memory_id in filtered_ids:
            memory = memories_by_id.get(memory_id)
            if not memory:
                continue

            rrf, similarity = rrf_scores[memory_id]
            recency = calculate_recency_factor(memory.last_accessed_at)

            # Adjusted score combines RRF with relevance and recency
            # Scale RRF (typically 0.01-0.03) to similarity-like range
            adjusted_score = (rrf * 30) * memory.relevance_score * recency

            results.append(
                MemorySearchResult(
                    memory=memory,
                    similarity=similarity,
                    adjusted_score=adjusted_score,
                )
            )

        logger.debug(
            "hybrid_search_complete",
            results_count=len(results),
            vector_candidates=len(vector_rows),
            keyword_candidates=len(keyword_rows),
            top_rrf_score=rrf_scores[results[0].memory.id][0] if results else None,
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
