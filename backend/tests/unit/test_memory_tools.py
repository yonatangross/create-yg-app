"""Unit tests for memory tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models.memory import AgentMemory, MemoryType
from app.shared.services.memory.memory_service import MemorySearchResult
from app.shared.services.memory.memory_tools import search_memory


class TestSearchMemoryTool:
    """Tests for search_memory LangChain tool."""

    @pytest.mark.asyncio
    async def test_search_memory_with_results(self):
        """Test successful search with results."""
        # Create mock memory
        mock_memory = MagicMock(spec=AgentMemory)
        mock_memory.content = "User prefers dark mode"
        mock_memory.memory_type = "user_preference"

        # Create mock search results
        mock_result = MemorySearchResult(
            memory=mock_memory,
            similarity=0.85,
            adjusted_score=0.85,
        )

        # Mock the service
        with (
            patch("app.shared.services.memory.memory_tools.get_session") as mock_get_session,
            patch(
                "app.shared.services.memory.memory_tools.get_embedding_service"
            ) as mock_get_embedding,
        ):
            # Setup async context manager
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_get_session.return_value.__aexit__.return_value = None

            # Setup embedding service
            mock_embedding_service = MagicMock()
            mock_get_embedding.return_value = mock_embedding_service

            # Setup memory service search
            with patch(
                "app.shared.services.memory.memory_tools.MemoryService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.search = AsyncMock(return_value=[mock_result])
                mock_service_class.return_value = mock_service

                result = await search_memory.ainvoke({"query": "theme preference"})

                # Verify result formatting
                assert "Found relevant memories:" in result
                assert "User Preference" in result
                assert "similarity: 85%" in result
                assert "User prefers dark mode" in result

                # Verify service was called correctly
                mock_service.search.assert_called_once_with(
                    query="theme preference",
                    memory_type=None,
                    limit=3,
                    threshold=0.6,
                )

    @pytest.mark.asyncio
    async def test_search_memory_with_no_results(self):
        """Test search with no matching memories."""
        with (
            patch("app.shared.services.memory.memory_tools.get_session") as mock_get_session,
            patch(
                "app.shared.services.memory.memory_tools.get_embedding_service"
            ) as mock_get_embedding,
        ):
            # Setup async context manager
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_get_session.return_value.__aexit__.return_value = None

            # Setup embedding service
            mock_embedding_service = MagicMock()
            mock_get_embedding.return_value = mock_embedding_service

            # Setup memory service with no results
            with patch(
                "app.shared.services.memory.memory_tools.MemoryService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.search = AsyncMock(return_value=[])
                mock_service_class.return_value = mock_service

                result = await search_memory.ainvoke({"query": "nonexistent topic"})

                assert result == "No relevant memories found for this query."

    @pytest.mark.asyncio
    async def test_search_memory_with_type_filter(self):
        """Test search with memory_type filter."""
        # Create mock memory
        mock_memory = MagicMock(spec=AgentMemory)
        mock_memory.content = "Analysis shows performance improvement"
        mock_memory.memory_type = "key_insight"

        mock_result = MemorySearchResult(
            memory=mock_memory,
            similarity=0.92,
            adjusted_score=0.92,
        )

        with (
            patch("app.shared.services.memory.memory_tools.get_session") as mock_get_session,
            patch(
                "app.shared.services.memory.memory_tools.get_embedding_service"
            ) as mock_get_embedding,
        ):
            # Setup async context manager
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_get_session.return_value.__aexit__.return_value = None

            # Setup embedding service
            mock_embedding_service = MagicMock()
            mock_get_embedding.return_value = mock_embedding_service

            # Setup memory service
            with patch(
                "app.shared.services.memory.memory_tools.MemoryService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.search = AsyncMock(return_value=[mock_result])
                mock_service_class.return_value = mock_service

                result = await search_memory.ainvoke(
                    {
                        "query": "previous analysis",
                        "memory_type": "key_insight",
                    }
                )

                # Verify type filter was applied
                mock_service.search.assert_called_once_with(
                    query="previous analysis",
                    memory_type=MemoryType.KEY_INSIGHT,
                    limit=3,
                    threshold=0.6,
                )

                assert "Key Insight" in result
                assert "Analysis shows performance improvement" in result

    @pytest.mark.asyncio
    async def test_search_memory_with_invalid_type(self):
        """Test search with invalid memory_type returns error."""
        result = await search_memory.ainvoke(
            {
                "query": "some query",
                "memory_type": "invalid_type",
            }
        )

        assert "Invalid memory_type 'invalid_type'" in result
        assert "Valid types:" in result
        assert "user_preference" in result
        assert "learned_fact" in result

    @pytest.mark.asyncio
    async def test_search_memory_with_multiple_results(self):
        """Test search returns multiple results formatted correctly."""
        # Create multiple mock memories
        mock_memories = [
            MagicMock(
                spec=AgentMemory,
                content="First memory",
                memory_type="user_preference",
            ),
            MagicMock(
                spec=AgentMemory,
                content="Second memory",
                memory_type="learned_fact",
            ),
            MagicMock(
                spec=AgentMemory,
                content="Third memory",
                memory_type="key_insight",
            ),
        ]

        mock_results = [
            MemorySearchResult(memory=mock_memories[0], similarity=0.95, adjusted_score=0.95),
            MemorySearchResult(memory=mock_memories[1], similarity=0.82, adjusted_score=0.82),
            MemorySearchResult(memory=mock_memories[2], similarity=0.75, adjusted_score=0.75),
        ]

        with (
            patch("app.shared.services.memory.memory_tools.get_session") as mock_get_session,
            patch(
                "app.shared.services.memory.memory_tools.get_embedding_service"
            ) as mock_get_embedding,
        ):
            # Setup async context manager
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_get_session.return_value.__aexit__.return_value = None

            # Setup embedding service
            mock_embedding_service = MagicMock()
            mock_get_embedding.return_value = mock_embedding_service

            # Setup memory service
            with patch(
                "app.shared.services.memory.memory_tools.MemoryService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.search = AsyncMock(return_value=mock_results)
                mock_service_class.return_value = mock_service

                result = await search_memory.ainvoke({"query": "test query"})

                # Verify all results are present
                assert "1. [User Preference] (similarity: 95%)" in result
                assert "First memory" in result
                assert "2. [Learned Fact] (similarity: 82%)" in result
                assert "Second memory" in result
                assert "3. [Key Insight] (similarity: 75%)" in result
                assert "Third memory" in result

    @pytest.mark.asyncio
    async def test_search_memory_handles_exceptions(self):
        """Test search handles database exceptions gracefully."""
        with (
            patch("app.shared.services.memory.memory_tools.get_session") as mock_get_session,
            patch(
                "app.shared.services.memory.memory_tools.get_embedding_service"
            ) as mock_get_embedding,
        ):
            # Setup async context manager
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_get_session.return_value.__aexit__.return_value = None

            # Setup embedding service
            mock_embedding_service = MagicMock()
            mock_get_embedding.return_value = mock_embedding_service

            # Setup memory service to raise exception
            with patch(
                "app.shared.services.memory.memory_tools.MemoryService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.search = AsyncMock(side_effect=Exception("Database connection error"))
                mock_service_class.return_value = mock_service

                result = await search_memory.ainvoke({"query": "test query"})

                assert "Error searching memory:" in result
                assert "Database connection error" in result

    @pytest.mark.asyncio
    async def test_search_memory_session_cleanup(self):
        """Test that database session is properly cleaned up."""
        with (
            patch("app.shared.services.memory.memory_tools.get_session") as mock_get_session,
            patch(
                "app.shared.services.memory.memory_tools.get_embedding_service"
            ) as mock_get_embedding,
        ):
            # Setup async context manager
            mock_session = AsyncMock()
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_context

            # Setup embedding service
            mock_embedding_service = MagicMock()
            mock_get_embedding.return_value = mock_embedding_service

            # Setup memory service
            with patch(
                "app.shared.services.memory.memory_tools.MemoryService"
            ) as mock_service_class:
                mock_service = MagicMock()
                mock_service.search = AsyncMock(return_value=[])
                mock_service_class.return_value = mock_service

                await search_memory.ainvoke({"query": "test"})

                # Verify context manager methods were called
                mock_context.__aenter__.assert_called_once()
                mock_context.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_memory_all_memory_types(self):
        """Test search works with all valid memory types."""
        valid_types = [
            "conversation_summary",
            "user_preference",
            "learned_fact",
            "key_insight",
        ]

        for memory_type in valid_types:
            with (
                patch("app.shared.services.memory.memory_tools.get_session") as mock_get_session,
                patch(
                    "app.shared.services.memory.memory_tools.get_embedding_service"
                ) as mock_get_embedding,
            ):
                # Setup async context manager
                mock_session = AsyncMock()
                mock_get_session.return_value.__aenter__.return_value = mock_session
                mock_get_session.return_value.__aexit__.return_value = None

                # Setup embedding service
                mock_embedding_service = MagicMock()
                mock_get_embedding.return_value = mock_embedding_service

                # Setup memory service
                with patch(
                    "app.shared.services.memory.memory_tools.MemoryService"
                ) as mock_service_class:
                    mock_service = MagicMock()
                    mock_service.search = AsyncMock(return_value=[])
                    mock_service_class.return_value = mock_service

                    result = await search_memory.ainvoke(
                        {
                            "query": "test",
                            "memory_type": memory_type,
                        }
                    )

                    # Should not return error for valid types
                    assert "Invalid memory_type" not in result
