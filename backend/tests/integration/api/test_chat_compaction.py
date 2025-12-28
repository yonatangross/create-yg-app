"""Integration tests for chat endpoint conversation compaction.

Tests verify that:
1. Chat endpoint loads existing conversation summary from PostgreSQL
2. Chat endpoint triggers compaction when message threshold exceeded
3. Streaming endpoint also supports compaction
4. Background tasks don't block the response
"""

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage, HumanMessage

from app.main import app
from app.shared.services.memory.compaction_service import CompactionResult


class TestChatCompactionIntegration:
    """Integration tests for chat with conversation compaction."""

    @pytest.fixture
    def mock_agent(self):
        """Create mock agent that returns predictable responses."""
        mock = MagicMock()

        async def mock_ainvoke(state):
            """Return response based on input."""
            query = state.get("query", "")
            conversation_summary = state.get("conversation_summary", "")

            # If summary exists, acknowledge it
            if conversation_summary:
                return {"response": f"I recall: {conversation_summary[:50]}... {query}"}

            return {"response": f"Received: {query}"}

        mock.ainvoke = mock_ainvoke

        # For streaming
        async def mock_astream_events(state, _version):  # noqa: ARG001
            query = state.get("query", "")
            conversation_summary = state.get("conversation_summary", "")

            response = (
                f"With summary: {query}"
                if conversation_summary
                else f"Received: {query}"
            )

            # Yield token events
            for word in response.split():
                yield {
                    "event": "on_chat_model_stream",
                    "data": {"chunk": MagicMock(content=word + " ")},
                }

        mock.astream_events = mock_astream_events
        return mock

    @pytest.fixture
    def mock_chat_history(self):
        """Create mock Redis chat history."""
        history = MagicMock()
        history.aget_messages = AsyncMock(return_value=[])
        history.aadd_messages = AsyncMock()
        return history

    @pytest.fixture
    def mock_memory_service(self):
        """Create mock memory service."""
        service = MagicMock()
        service.proactive_recall = AsyncMock(return_value="")
        return service

    @pytest.fixture
    def mock_compactor(self):
        """Create mock SessionCompactor."""
        compactor = MagicMock()

        # Default: no existing summary
        compactor.get_context_with_summary = AsyncMock(return_value=(None, []))

        # Default: no compaction needed
        compactor.compact = AsyncMock(
            return_value=CompactionResult(
                summary=None,
                recent_messages=[],
                was_compacted=False,
                original_count=0,
                compacted_count=0,
            )
        )
        return compactor

    @pytest.mark.asyncio
    async def test_chat_loads_existing_conversation_summary(
        self, mock_agent, mock_chat_history, mock_memory_service, mock_compactor
    ):
        """Test that chat endpoint loads existing conversation summary."""
        # Setup: Return existing summary
        existing_summary = "User previously discussed React hooks and state management."
        mock_compactor.get_context_with_summary = AsyncMock(return_value=(existing_summary, []))

        with (
            patch("app.api.v1.chat.get_agent", return_value=mock_agent),
            patch("app.api.v1.chat.get_chat_history", return_value=mock_chat_history),
            patch("app.api.v1.chat.get_session") as mock_get_session,
            patch("app.api.v1.chat.SessionCompactor", return_value=mock_compactor),
            patch("app.api.v1.chat.MemoryService", return_value=mock_memory_service),
        ):
            # Setup session context manager
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_session

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/v1/chat",
                    json={"message": "What hooks did we discuss?", "conversation_id": "test-conv"},
                )

                assert response.status_code == 200
                data = response.json()

                # Verify summary was loaded
                mock_compactor.get_context_with_summary.assert_called_once()

                # Verify agent received the summary in context
                # The mock_agent returns response that includes summary
                assert "I recall:" in data["response"]

    @pytest.mark.asyncio
    async def test_chat_triggers_compaction_when_threshold_exceeded(
        self, mock_agent, mock_chat_history, mock_memory_service, mock_compactor
    ):
        """Test that chat endpoint triggers compaction in background when threshold exceeded."""
        # Setup: Many messages that should trigger compaction
        long_history = [
            HumanMessage(content=f"Message {i}")
            if i % 2 == 0
            else AIMessage(content=f"Response {i}")
            for i in range(20)  # 20 messages > 15 threshold
        ]
        mock_chat_history.aget_messages = AsyncMock(return_value=long_history)

        # Mock compaction to return a result showing it was compacted
        compaction_result = CompactionResult(
            summary="Summary of messages 0-10",
            recent_messages=long_history[-10:],
            was_compacted=True,
            original_count=22,  # 20 existing + 2 new
            compacted_count=12,
        )
        mock_compactor.compact = AsyncMock(return_value=compaction_result)

        # Track background task creation
        background_tasks = []

        original_create_task = asyncio.create_task

        def mock_create_task(coro):
            task = original_create_task(coro)
            background_tasks.append(task)
            return task

        with (
            patch("app.api.v1.chat.get_agent", return_value=mock_agent),
            patch("app.api.v1.chat.get_chat_history", return_value=mock_chat_history),
            patch("app.api.v1.chat.get_session") as mock_get_session,
            patch("app.api.v1.chat.SessionCompactor", return_value=mock_compactor),
            patch("app.api.v1.chat.MemoryService", return_value=mock_memory_service),
            patch("app.api.v1.chat.asyncio.create_task", side_effect=mock_create_task),
        ):
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_session

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/v1/chat",
                    json={"message": "New message", "conversation_id": "long-conv"},
                )

                assert response.status_code == 200

                # Wait a bit for background tasks to start
                await asyncio.sleep(0.1)

                # Verify background compaction task was created
                assert len(background_tasks) > 0

                # Clean up tasks
                for task in background_tasks:
                    if not task.done():
                        task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await task

    @pytest.mark.asyncio
    async def test_streaming_endpoint_loads_conversation_summary(
        self, mock_agent, mock_chat_history, mock_memory_service, mock_compactor
    ):
        """Test that streaming endpoint also loads conversation summary."""
        # Setup: Return existing summary
        existing_summary = "Previous context about API design."
        mock_compactor.get_context_with_summary = AsyncMock(return_value=(existing_summary, []))

        with (
            patch("app.api.v1.chat.get_agent", return_value=mock_agent),
            patch("app.api.v1.chat.get_chat_history", return_value=mock_chat_history),
            patch("app.api.v1.chat.get_session") as mock_get_session,
            patch("app.api.v1.chat.SessionCompactor", return_value=mock_compactor),
            patch("app.api.v1.chat.MemoryService", return_value=mock_memory_service),
        ):
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_session

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/v1/chat/stream",
                    json={"message": "Continue discussion", "conversation_id": "stream-conv"},
                )

                assert response.status_code == 200

                # Verify summary was loaded
                mock_compactor.get_context_with_summary.assert_called_once()

                # Read stream events
                events = []
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        events.append(line)

                # Verify stream completed
                assert len(events) > 0

    @pytest.mark.asyncio
    async def test_streaming_endpoint_triggers_compaction(
        self, mock_chat_history, mock_memory_service, mock_compactor
    ):
        """Test that streaming endpoint triggers compaction in background."""
        # Setup: Long history
        long_history = [
            HumanMessage(content=f"Msg {i}") if i % 2 == 0 else AIMessage(content=f"Resp {i}")
            for i in range(18)
        ]
        mock_chat_history.aget_messages = AsyncMock(return_value=long_history)

        # Create a fresh mock agent for this specific test to avoid parameter issues
        fresh_mock_agent = MagicMock()

        async def working_astream_events(state, version):  # noqa: ARG001
            query = state.get("query", "")
            response = f"Stream: {query}"

            # Yield token events
            for word in response.split():
                yield {
                    "event": "on_chat_model_stream",
                    "data": {"chunk": MagicMock(content=word + " ")},
                }

        fresh_mock_agent.astream_events = working_astream_events

        # Track background task creation
        background_tasks = []

        original_create_task = asyncio.create_task

        def mock_create_task(coro):
            task = original_create_task(coro)
            background_tasks.append(task)
            return task

        with (
            patch("app.api.v1.chat.get_agent", return_value=fresh_mock_agent),
            patch("app.api.v1.chat.get_chat_history", return_value=mock_chat_history),
            patch("app.api.v1.chat.get_session") as mock_get_session,
            patch("app.api.v1.chat.SessionCompactor", return_value=mock_compactor),
            patch("app.api.v1.chat.MemoryService", return_value=mock_memory_service),
            patch("app.api.v1.chat.asyncio.create_task", side_effect=mock_create_task),
        ):
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_session

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/v1/chat/stream",
                    json={"message": "New message", "conversation_id": "stream-compact"},
                )

                assert response.status_code == 200

                # Consume the stream
                async for _ in response.aiter_lines():
                    pass

                # Wait for background tasks
                await asyncio.sleep(0.1)

                # Verify background tasks were created
                assert len(background_tasks) > 0

                # Clean up
                for task in background_tasks:
                    if not task.done():
                        task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await task

    @pytest.mark.asyncio
    async def test_background_compaction_does_not_block_response(
        self, mock_agent, mock_chat_history, mock_memory_service, mock_compactor
    ):
        """Test that background compaction doesn't block the API response."""
        import time

        # Setup: Simulate slow compaction
        async def slow_compact(*args, **kwargs):  # noqa: ARG001
            await asyncio.sleep(0.5)  # Simulate slow operation
            return CompactionResult(
                summary="Slow summary",
                recent_messages=[],
                was_compacted=True,
                original_count=20,
                compacted_count=10,
            )

        mock_compactor.compact = slow_compact

        # Long history to trigger compaction
        long_history = [
            HumanMessage(content=f"M {i}") if i % 2 == 0 else AIMessage(content=f"R {i}")
            for i in range(20)
        ]
        mock_chat_history.aget_messages = AsyncMock(return_value=long_history)

        with (
            patch("app.api.v1.chat.get_agent", return_value=mock_agent),
            patch("app.api.v1.chat.get_chat_history", return_value=mock_chat_history),
            patch("app.api.v1.chat.get_session") as mock_get_session,
            patch("app.api.v1.chat.SessionCompactor", return_value=mock_compactor),
            patch("app.api.v1.chat.MemoryService", return_value=mock_memory_service),
        ):
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_session

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                start_time = time.time()

                response = await client.post(
                    "/api/v1/chat",
                    json={"message": "Test", "conversation_id": "fast-response"},
                )

                end_time = time.time()
                response_time = end_time - start_time

                assert response.status_code == 200

                # Response should be fast, not blocked by 0.5s background compaction
                # Using 1.0s threshold to account for CI/test overhead while still
                # verifying the 0.5s compaction doesn't block (would take > 1s if blocking)
                assert response_time < 1.0, f"Response took {response_time}s, should be < 1.0s"

    @pytest.mark.asyncio
    async def test_compaction_with_no_existing_summary(
        self, mock_agent, mock_chat_history, mock_memory_service, mock_compactor
    ):
        """Test compaction flow when no existing summary exists."""
        # Setup: No existing summary
        mock_compactor.get_context_with_summary = AsyncMock(return_value=(None, []))

        with (
            patch("app.api.v1.chat.get_agent", return_value=mock_agent),
            patch("app.api.v1.chat.get_chat_history", return_value=mock_chat_history),
            patch("app.api.v1.chat.get_session") as mock_get_session,
            patch("app.api.v1.chat.SessionCompactor", return_value=mock_compactor),
            patch("app.api.v1.chat.MemoryService", return_value=mock_memory_service),
        ):
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_session

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/v1/chat",
                    json={"message": "First message", "conversation_id": "new-conv"},
                )

                assert response.status_code == 200
                data = response.json()

                # Should work normally even without summary
                assert "response" in data
                assert data["conversation_id"] == "new-conv"

    @pytest.mark.asyncio
    async def test_compaction_handles_summary_load_failure(
        self, mock_agent, mock_chat_history, mock_memory_service, mock_compactor
    ):
        """Test that summary load failure doesn't break the request."""
        # Setup: Simulate summary load failure
        mock_compactor.get_context_with_summary = AsyncMock(side_effect=Exception("Database error"))

        with (
            patch("app.api.v1.chat.get_agent", return_value=mock_agent),
            patch("app.api.v1.chat.get_chat_history", return_value=mock_chat_history),
            patch("app.api.v1.chat.get_session") as mock_get_session,
            patch("app.api.v1.chat.SessionCompactor", return_value=mock_compactor),
            patch("app.api.v1.chat.MemoryService", return_value=mock_memory_service),
        ):
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_session

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/v1/chat",
                    json={"message": "Test message", "conversation_id": "error-conv"},
                )

                # Should still succeed with degraded mode (no summary)
                assert response.status_code == 200
                data = response.json()
                assert "response" in data

    @pytest.mark.asyncio
    async def test_compaction_timeout_handling(
        self, mock_agent, mock_chat_history, mock_memory_service, mock_compactor
    ):
        """Test that summary load timeout is handled gracefully."""

        # Setup: Simulate slow summary load
        async def slow_summary_load(*args, **kwargs):  # noqa: ARG001
            await asyncio.sleep(5.0)  # Exceed timeout
            return ("Summary", [])

        mock_compactor.get_context_with_summary = slow_summary_load

        with (
            patch("app.api.v1.chat.get_agent", return_value=mock_agent),
            patch("app.api.v1.chat.get_chat_history", return_value=mock_chat_history),
            patch("app.api.v1.chat.get_session") as mock_get_session,
            patch("app.api.v1.chat.SessionCompactor", return_value=mock_compactor),
            patch("app.api.v1.chat.MemoryService", return_value=mock_memory_service),
        ):
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_session

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/v1/chat",
                    json={"message": "Test", "conversation_id": "timeout-conv"},
                    timeout=10.0,
                )

                # Should complete despite summary load timeout
                assert response.status_code == 200
                data = response.json()
                assert "response" in data

    @pytest.mark.asyncio
    async def test_multiple_conversations_have_separate_summaries(
        self, mock_agent, mock_chat_history, mock_memory_service, mock_compactor
    ):
        """Test that different conversations load their own summaries."""
        # Setup: Different summaries for different conversations
        summaries = {
            "conv-1": "Summary for conversation 1",
            "conv-2": "Summary for conversation 2",
        }

        async def get_summary_by_conv(messages, conversation_id):
            return (summaries.get(conversation_id), messages)

        mock_compactor.get_context_with_summary = AsyncMock(side_effect=get_summary_by_conv)

        with (
            patch("app.api.v1.chat.get_agent", return_value=mock_agent),
            patch("app.api.v1.chat.get_chat_history", return_value=mock_chat_history),
            patch("app.api.v1.chat.get_session") as mock_get_session,
            patch("app.api.v1.chat.SessionCompactor", return_value=mock_compactor),
            patch("app.api.v1.chat.MemoryService", return_value=mock_memory_service),
        ):
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_get_session.return_value = mock_session

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                # Request conv-1
                response1 = await client.post(
                    "/api/v1/chat",
                    json={"message": "Hello", "conversation_id": "conv-1"},
                )

                # Request conv-2
                response2 = await client.post(
                    "/api/v1/chat",
                    json={"message": "Hello", "conversation_id": "conv-2"},
                )

                assert response1.status_code == 200
                assert response2.status_code == 200

                # Verify both conversations were handled
                assert mock_compactor.get_context_with_summary.call_count == 2

                # Verify correct conversation IDs were used
                calls = mock_compactor.get_context_with_summary.call_args_list
                conv_ids = [call[0][1] for call in calls]
                assert "conv-1" in conv_ids
                assert "conv-2" in conv_ids
