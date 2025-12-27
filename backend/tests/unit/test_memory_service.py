"""Unit tests for MemoryService."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models.memory import AgentMemory, ConversationSummary, MemoryType
from app.shared.services.memory.memory_service import MemorySearchResult, MemoryService


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
        self, memory_service, mock_session, mock_embedding_service  # noqa: ARG002
    ):
        """Test search returns MemorySearchResult with similarity scores."""
        # Setup mock query result
        mock_memory = MagicMock(spec=AgentMemory)
        mock_memory.id = uuid.uuid4()
        mock_memory.content = "Test memory"
        mock_memory.memory_type = MemoryType.LEARNED_FACT

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
        self, memory_service, mock_session, mock_embedding_service  # noqa: ARG002
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
        self, memory_service, mock_session, mock_embedding_service  # noqa: ARG002
    ):
        """Test proactive recall returns formatted memory context."""
        # Setup mock search results
        mock_memory = MagicMock(spec=AgentMemory)
        mock_memory.content = "User likes pizza"
        mock_memory.memory_type = MagicMock(value="user_preference")

        mock_result = MagicMock()
        mock_result.all.return_value = [MagicMock(AgentMemory=mock_memory, distance=0.1)]
        mock_session.execute.return_value = mock_result

        result = await memory_service.proactive_recall("What food do I like?")

        assert "Relevant Context from Memory" in result
        assert "User Preference" in result
        assert "User likes pizza" in result

    @pytest.mark.asyncio
    async def test_proactive_recall_empty_when_no_matches(
        self, memory_service, mock_session, mock_embedding_service  # noqa: ARG002
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
