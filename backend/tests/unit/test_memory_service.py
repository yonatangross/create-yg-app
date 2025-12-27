"""Unit tests for MemoryService."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models.memory import AgentMemory, ConversationSummary, MemoryType
from app.shared.services.memory.memory_service import (
    MemorySearchResult,
    MemoryService,
    calculate_recency_factor,
)


class TestMemoryService:
    """Tests for MemoryService."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async database session."""
        session = MagicMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()
        session.delete = AsyncMock()
        return session

    @pytest.fixture
    def mock_embedding_service(self):
        """Create mock embedding service."""
        service = MagicMock()
        service.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
        return service

    @pytest.fixture
    def memory_service(self, mock_session, mock_embedding_service):
        """Create MemoryService with mocked dependencies."""
        return MemoryService(mock_session, mock_embedding_service)

    @pytest.mark.asyncio
    async def test_store_creates_memory_with_embedding(
        self, memory_service, mock_session, mock_embedding_service
    ):
        """Test storing memory generates embedding and saves."""
        content = "User prefers dark mode"

        await memory_service.store(
            content=content,
            memory_type=MemoryType.USER_PREFERENCE,
            conversation_id="conv-123",
            metadata={"source": "settings"},
        )

        # Verify embedding was generated
        mock_embedding_service.generate_embedding.assert_called_once_with(content)

        # Verify memory was added to session
        mock_session.add.assert_called_once()
        added_memory = mock_session.add.call_args[0][0]
        assert isinstance(added_memory, AgentMemory)
        assert added_memory.content == content
        assert added_memory.memory_type == MemoryType.USER_PREFERENCE
        assert added_memory.conversation_id == "conv-123"

        # Verify commit was called
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_with_default_values(self, memory_service, mock_session):
        """Test storing memory with minimal parameters."""
        await memory_service.store(
            content="Test content",
            memory_type=MemoryType.LEARNED_FACT,
        )

        added_memory = mock_session.add.call_args[0][0]
        assert added_memory.conversation_id is None
        assert added_memory.relevance_score == 1.0
        assert added_memory.memory_metadata == {}

    @pytest.mark.asyncio
    async def test_search_returns_results_with_similarity(
        self,
        memory_service,
        mock_session,
        mock_embedding_service,  # noqa: ARG002
    ):
        """Test search returns MemorySearchResult with similarity scores."""
        # Setup mock query result
        mock_memory = MagicMock(spec=AgentMemory)
        mock_memory.id = uuid.uuid4()
        mock_memory.content = "Test memory"
        mock_memory.memory_type = MemoryType.LEARNED_FACT
        mock_memory.relevance_score = 1.0
        mock_memory.last_accessed_at = None

        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(AgentMemory=mock_memory, distance=0.2)  # distance 0.2 = similarity 0.8
        ]
        mock_session.execute.return_value = mock_result

        results = await memory_service.search("query text", limit=5, threshold=0.7)

        assert len(results) == 1
        assert isinstance(results[0], MemorySearchResult)
        assert results[0].memory == mock_memory
        assert results[0].similarity == pytest.approx(0.8, abs=0.01)
        assert results[0].adjusted_score == pytest.approx(0.8, abs=0.01)  # 0.8 * 1.0 * 1.0

    @pytest.mark.asyncio
    async def test_search_generates_query_embedding(
        self, memory_service, mock_embedding_service, mock_session
    ):
        """Test search generates embedding for query."""
        mock_session.execute.return_value = MagicMock(all=MagicMock(return_value=[]))

        await memory_service.search("search query")

        mock_embedding_service.generate_embedding.assert_called_once_with("search query")

    @pytest.mark.asyncio
    async def test_search_filters_by_memory_type(
        self,
        memory_service,
        mock_session,
        mock_embedding_service,  # noqa: ARG002
    ):
        """Test search can filter by memory type."""
        mock_session.execute.return_value = MagicMock(all=MagicMock(return_value=[]))

        await memory_service.search(
            "query",
            memory_type=MemoryType.USER_PREFERENCE,
        )

        # The filter is applied in the SQL query
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_proactive_recall_returns_formatted_context(
        self,
        memory_service,
        mock_session,
        mock_embedding_service,  # noqa: ARG002
    ):
        """Test proactive recall returns formatted memory context."""
        # Setup mock search results
        mock_memory = MagicMock(spec=AgentMemory)
        mock_memory.id = uuid.uuid4()
        mock_memory.content = "User likes pizza"
        mock_memory.memory_type = MagicMock(value="user_preference")
        mock_memory.relevance_score = 1.0
        mock_memory.last_accessed_at = None

        mock_result = MagicMock()
        mock_result.all.return_value = [MagicMock(AgentMemory=mock_memory, distance=0.1)]
        mock_session.execute.return_value = mock_result

        result = await memory_service.proactive_recall("What food do I like?")

        assert "Relevant Context from Memory" in result
        assert "User Preference" in result
        assert "User likes pizza" in result

    @pytest.mark.asyncio
    async def test_proactive_recall_empty_when_no_matches(
        self,
        memory_service,
        mock_session,
        mock_embedding_service,  # noqa: ARG002
    ):
        """Test proactive recall returns empty string when no matches."""
        mock_session.execute.return_value = MagicMock(all=MagicMock(return_value=[]))

        result = await memory_service.proactive_recall("Random query")

        assert result == ""

    @pytest.mark.asyncio
    async def test_get_conversation_summary_returns_summary(self, memory_service, mock_session):
        """Test getting conversation summary."""
        mock_summary = MagicMock(spec=ConversationSummary)
        mock_summary.conversation_id = "conv-123"
        mock_summary.summary = "Discussion about preferences"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_summary
        mock_session.execute.return_value = mock_result

        result = await memory_service.get_conversation_summary("conv-123")

        assert result == mock_summary

    @pytest.mark.asyncio
    async def test_get_conversation_summary_returns_none_when_not_found(
        self, memory_service, mock_session
    ):
        """Test getting non-existent conversation summary."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await memory_service.get_conversation_summary("non-existent")

        assert result is None

    @pytest.mark.asyncio
    async def test_save_conversation_summary_creates_new(self, memory_service, mock_session):
        """Test saving new conversation summary."""
        # No existing summary
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await memory_service.save_conversation_summary(
            conversation_id="conv-new",
            summary="New summary",
            message_count=10,
        )

        # Should create new ConversationSummary
        assert mock_session.add.call_count >= 1

    @pytest.mark.asyncio
    async def test_save_conversation_summary_updates_existing(self, memory_service, mock_session):
        """Test updating existing conversation summary."""
        # Existing summary
        existing = MagicMock(spec=ConversationSummary)
        existing.summary = "Old summary"
        existing.message_count = 5

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_session.execute.return_value = mock_result

        await memory_service.save_conversation_summary(
            conversation_id="conv-existing",
            summary="Updated summary",
            message_count=15,
        )

        # Should update existing
        assert existing.summary == "Updated summary"
        assert existing.message_count == 15

    @pytest.mark.asyncio
    async def test_delete_memory_returns_true_when_found(self, memory_service, mock_session):
        """Test deleting existing memory returns True."""
        mock_memory = MagicMock(spec=AgentMemory)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_memory
        mock_session.execute.return_value = mock_result

        result = await memory_service.delete_memory(uuid.uuid4())

        assert result is True
        mock_session.delete.assert_called_once_with(mock_memory)

    @pytest.mark.asyncio
    async def test_delete_memory_returns_false_when_not_found(self, memory_service, mock_session):
        """Test deleting non-existent memory returns False."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await memory_service.delete_memory(uuid.uuid4())

        assert result is False
        mock_session.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_memories_by_type(self, memory_service, mock_session):
        """Test getting memories filtered by type."""
        mock_memories = [MagicMock(spec=AgentMemory), MagicMock(spec=AgentMemory)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_memories
        mock_session.execute.return_value = mock_result

        results = await memory_service.get_memories_by_type(MemoryType.USER_PREFERENCE, limit=10)

        assert len(results) == 2
        mock_session.execute.assert_called_once()


class TestRecencyFactor:
    """Tests for calculate_recency_factor function."""

    def test_recency_factor_none_returns_one(self):
        """Test that None (never accessed) returns 1.0."""
        result = calculate_recency_factor(None)
        assert result == 1.0

    def test_recency_factor_today_returns_one(self):
        """Test that today's access returns 1.0."""
        now = datetime.now(UTC)
        result = calculate_recency_factor(now)
        assert result == pytest.approx(1.0, abs=0.01)

    def test_recency_factor_one_year_old_returns_half(self):
        """Test that 1 year old returns 0.5."""
        one_year_ago = datetime.now(UTC) - timedelta(days=365)
        result = calculate_recency_factor(one_year_ago)
        assert result == pytest.approx(0.5, abs=0.01)

    def test_recency_factor_six_months_returns_point_seven_five(self):
        """Test that 6 months old returns ~0.75."""
        six_months_ago = datetime.now(UTC) - timedelta(days=182)
        result = calculate_recency_factor(six_months_ago)
        # 1.0 - (182/365)*0.5 ≈ 0.75
        assert result == pytest.approx(0.75, abs=0.05)

    def test_recency_factor_very_old_capped_at_half(self):
        """Test that very old memories are capped at 0.5."""
        very_old = datetime.now(UTC) - timedelta(days=730)  # 2 years
        result = calculate_recency_factor(very_old)
        assert result == 0.5


class TestMemoryServiceRelevanceDecay:
    """Tests for relevance decay functionality."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async database session."""
        session = MagicMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()
        session.delete = AsyncMock()
        return session

    @pytest.fixture
    def mock_embedding_service(self):
        """Create mock embedding service."""
        service = MagicMock()
        service.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
        return service

    @pytest.fixture
    def memory_service(self, mock_session, mock_embedding_service):
        """Create MemoryService with mocked dependencies."""
        return MemoryService(mock_session, mock_embedding_service)

    @pytest.mark.asyncio
    async def test_search_includes_adjusted_score(
        self,
        memory_service,
        mock_session,
        mock_embedding_service,  # noqa: ARG002
    ):
        """Test search returns adjusted scores with recency factor."""
        # Setup mock memory with last_accessed_at
        mock_memory = MagicMock(spec=AgentMemory)
        mock_memory.id = uuid.uuid4()
        mock_memory.content = "Test memory"
        mock_memory.memory_type = MemoryType.LEARNED_FACT
        mock_memory.relevance_score = 1.0
        mock_memory.last_accessed_at = datetime.now(UTC) - timedelta(days=182)

        mock_result = MagicMock()
        mock_result.all.return_value = [MagicMock(AgentMemory=mock_memory, distance=0.2)]
        mock_session.execute.return_value = mock_result

        results = await memory_service.search("query text", limit=5, threshold=0.7)

        assert len(results) == 1
        assert isinstance(results[0], MemorySearchResult)
        assert results[0].similarity == pytest.approx(0.8, abs=0.01)
        # Adjusted score = similarity * relevance * recency
        # 0.8 * 1.0 * ~0.75 ≈ 0.6
        assert results[0].adjusted_score == pytest.approx(0.6, abs=0.1)

    @pytest.mark.asyncio
    async def test_search_filters_by_agent_type(
        self,
        memory_service,
        mock_session,
        mock_embedding_service,  # noqa: ARG002
    ):
        """Test search filters memories by agent type."""
        mock_session.execute.return_value = MagicMock(all=MagicMock(return_value=[]))

        await memory_service.search("query", agent_type="chat")

        # Verify execute was called (filtering happens in SQL)
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_proactive_recall_tracks_access(
        self,
        memory_service,
        mock_session,
        mock_embedding_service,  # noqa: ARG002
    ):
        """Test proactive recall tracks memory access."""
        # Setup mock search results
        mock_memory = MagicMock(spec=AgentMemory)
        mock_memory.id = uuid.uuid4()
        mock_memory.content = "User likes pizza"
        mock_memory.memory_type = MagicMock(value="user_preference")
        mock_memory.relevance_score = 0.8
        mock_memory.last_accessed_at = None

        mock_result = MagicMock()
        mock_result.all.return_value = [MagicMock(AgentMemory=mock_memory, distance=0.1)]
        mock_session.execute.return_value = mock_result

        await memory_service.proactive_recall("What food do I like?")

        # Verify commit was called (for tracking access)
        assert mock_session.commit.call_count >= 1

    @pytest.mark.asyncio
    async def test_proactive_recall_for_agent(
        self,
        memory_service,
        mock_session,
        mock_embedding_service,  # noqa: ARG002
    ):
        """Test proactive recall for specific agent type."""
        # Setup mock search results
        mock_memory = MagicMock(spec=AgentMemory)
        mock_memory.id = uuid.uuid4()
        mock_memory.content = "Code review insight"
        mock_memory.memory_type = MagicMock(value="key_insight")
        mock_memory.relevance_score = 0.9
        mock_memory.last_accessed_at = None

        mock_result = MagicMock()
        mock_result.all.return_value = [MagicMock(AgentMemory=mock_memory, distance=0.15)]
        mock_session.execute.return_value = mock_result

        result = await memory_service.proactive_recall_for_agent(
            "Review this code",
            agent_type="code_review",
        )

        assert "Relevant Context from Memory" in result
        assert "Key Insight" in result
        assert "Code review insight" in result

    @pytest.mark.asyncio
    async def test_track_memory_access_empty_list(self, memory_service, mock_session):
        """Test _track_memory_access handles empty list."""
        await memory_service._track_memory_access([])

        # Should not execute any queries
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_sorts_by_adjusted_score(
        self,
        memory_service,
        mock_session,
        mock_embedding_service,  # noqa: ARG002
    ):
        """Test search sorts results by adjusted score, not just similarity."""
        # Setup two memories: one older with high similarity, one newer with lower similarity
        memory1 = MagicMock(spec=AgentMemory)
        memory1.id = uuid.uuid4()
        memory1.content = "Old memory"
        memory1.memory_type = MemoryType.LEARNED_FACT
        memory1.relevance_score = 1.0
        memory1.last_accessed_at = datetime.now(UTC) - timedelta(days=365)  # Very old

        memory2 = MagicMock(spec=AgentMemory)
        memory2.id = uuid.uuid4()
        memory2.content = "Recent memory"
        memory2.memory_type = MemoryType.LEARNED_FACT
        memory2.relevance_score = 1.0
        memory2.last_accessed_at = datetime.now(UTC)  # Today

        mock_result = MagicMock()
        # memory1 has higher similarity (0.9) but is old
        # memory2 has lower similarity (0.7) but is recent
        mock_result.all.return_value = [
            MagicMock(AgentMemory=memory1, distance=0.1),  # similarity 0.9
            MagicMock(AgentMemory=memory2, distance=0.3),  # similarity 0.7
        ]
        mock_session.execute.return_value = mock_result

        results = await memory_service.search("query", limit=5, threshold=0.6)

        # memory2 should rank first due to recency despite lower similarity
        # memory2 adjusted: 0.7 * 1.0 * 1.0 = 0.7
        # memory1 adjusted: 0.9 * 1.0 * 0.5 = 0.45
        assert len(results) == 2
        assert results[0].memory == memory2
        assert results[1].memory == memory1
