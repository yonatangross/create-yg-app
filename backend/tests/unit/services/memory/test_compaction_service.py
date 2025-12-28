"""Comprehensive unit tests for conversation compaction service.

Tests the compaction service that compresses long conversations into summaries
while preserving recent messages for context efficiency.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.shared.services.memory.compaction_service import (
    CompactionConfig,
    CompactionResult,
    SessionCompactor,
    compact_if_needed,
)


class TestCompactionConfig:
    """Tests for CompactionConfig dataclass."""

    def test_default_config_values(self):
        """Test that default configuration has expected values."""
        config = CompactionConfig()

        assert config.max_turns_verbatim == 5
        assert config.compaction_threshold == 15
        assert config.summary_max_tokens == 500
        assert config.preserve_system_messages is True

    def test_custom_config_values(self):
        """Test that custom configuration values are set correctly."""
        config = CompactionConfig(
            max_turns_verbatim=10,
            compaction_threshold=20,
            summary_max_tokens=1000,
            preserve_system_messages=False,
        )

        assert config.max_turns_verbatim == 10
        assert config.compaction_threshold == 20
        assert config.summary_max_tokens == 1000
        assert config.preserve_system_messages is False

    def test_config_is_immutable_dataclass(self):
        """Test that config is a dataclass (can be instantiated with kwargs)."""
        config = CompactionConfig(max_turns_verbatim=3)
        assert config.max_turns_verbatim == 3
        # Other values should be defaults
        assert config.compaction_threshold == 15


class TestCompactionResult:
    """Tests for CompactionResult dataclass."""

    def test_compaction_result_creation(self):
        """Test creating a CompactionResult."""
        messages = [HumanMessage(content="Hello"), AIMessage(content="Hi")]
        result = CompactionResult(
            summary="Previous conversation about greetings.",
            recent_messages=messages,
            was_compacted=True,
            original_count=10,
            compacted_count=8,
        )

        assert result.summary == "Previous conversation about greetings."
        assert result.recent_messages == messages
        assert result.was_compacted is True
        assert result.original_count == 10
        assert result.compacted_count == 8

    def test_compaction_result_no_compaction(self):
        """Test CompactionResult when no compaction occurred."""
        messages = [HumanMessage(content="Hello")]
        result = CompactionResult(
            summary=None,
            recent_messages=messages,
            was_compacted=False,
            original_count=1,
            compacted_count=0,
        )

        assert result.summary is None
        assert result.was_compacted is False
        assert result.compacted_count == 0


class TestSessionCompactor:
    """Tests for SessionCompactor class."""

    @pytest.fixture
    def mock_memory_service(self):
        """Create mock memory service."""
        service = MagicMock()
        service.get_conversation_summary = AsyncMock(return_value=None)
        service.save_conversation_summary = AsyncMock()
        return service

    @pytest.fixture
    def compactor(self, mock_memory_service):
        """Create SessionCompactor with mocked dependencies."""
        return SessionCompactor(
            memory_service=mock_memory_service,
            config=None,  # Use defaults
            model="gpt-4o-mini",
        )

    @pytest.fixture
    def custom_compactor(self, mock_memory_service):
        """Create SessionCompactor with custom config."""
        config = CompactionConfig(
            max_turns_verbatim=3,
            compaction_threshold=6,
            summary_max_tokens=200,
        )
        return SessionCompactor(
            memory_service=mock_memory_service,
            config=config,
            model="gpt-4o-mini",
        )

    def test_compactor_initialization(self, mock_memory_service):
        """Test SessionCompactor initialization."""
        compactor = SessionCompactor(
            memory_service=mock_memory_service,
            config=None,
            model="gpt-4o-mini",
        )

        assert compactor.memory_service == mock_memory_service
        assert compactor.config.max_turns_verbatim == 5
        assert compactor.model == "gpt-4o-mini"
        assert compactor._llm is None  # Lazy loaded

    def test_compactor_with_custom_config(self, mock_memory_service):
        """Test SessionCompactor with custom configuration."""
        config = CompactionConfig(max_turns_verbatim=10)
        compactor = SessionCompactor(
            memory_service=mock_memory_service,
            config=config,
            model="gpt-4o",
        )

        assert compactor.config.max_turns_verbatim == 10
        assert compactor.model == "gpt-4o"

    def test_split_messages_below_threshold(self, compactor):
        """Test _split_messages when message count is below threshold."""
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi"),
            HumanMessage(content="How are you?"),
            AIMessage(content="Good!"),
        ]

        to_summarize, recent = compactor._split_messages(messages)

        # With max_turns_verbatim=5 (10 messages), all 4 messages should be kept
        assert to_summarize == []
        assert recent == messages

    def test_split_messages_above_threshold(self, compactor):
        """Test _split_messages when message count exceeds threshold."""
        # Create 12 messages (6 turns)
        messages = []
        for i in range(6):
            messages.append(HumanMessage(content=f"User {i}"))
            messages.append(AIMessage(content=f"Assistant {i}"))

        to_summarize, recent = compactor._split_messages(messages)

        # With max_turns_verbatim=5 (10 messages), last 10 should be kept
        # First 2 messages should be summarized
        assert len(to_summarize) == 2
        assert len(recent) == 10
        assert to_summarize[0].content == "User 0"
        assert recent[0].content == "User 1"
        assert recent[-1].content == "Assistant 5"

    def test_split_messages_exact_threshold(self, compactor):
        """Test _split_messages when exactly at threshold."""
        # Create exactly 10 messages (5 turns)
        messages = []
        for i in range(5):
            messages.append(HumanMessage(content=f"User {i}"))
            messages.append(AIMessage(content=f"Assistant {i}"))

        to_summarize, recent = compactor._split_messages(messages)

        # All messages should be kept
        assert to_summarize == []
        assert recent == messages

    def test_format_messages_for_summary_basic(self, compactor):
        """Test _format_messages_for_summary with basic messages."""
        messages = [
            HumanMessage(content="What is AI?"),
            AIMessage(content="AI is artificial intelligence."),
        ]

        formatted = compactor._format_messages_for_summary(messages)

        assert "User: What is AI?" in formatted
        assert "Assistant: AI is artificial intelligence." in formatted

    def test_format_messages_for_summary_skips_system_messages(self, compactor):
        """Test that SystemMessages are skipped in summary formatting."""
        messages = [
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content="Hello"),
            AIMessage(content="Hi"),
        ]

        formatted = compactor._format_messages_for_summary(messages)

        assert "System:" not in formatted
        assert "User: Hello" in formatted
        assert "Assistant: Hi" in formatted

    def test_format_messages_for_summary_truncates_long_content(self, compactor):
        """Test that long messages are truncated to 500 characters."""
        long_content = "x" * 1000
        messages = [HumanMessage(content=long_content)]

        formatted = compactor._format_messages_for_summary(messages)

        # Should be truncated to 500 chars + "..."
        assert "..." in formatted
        assert len(formatted) < len(long_content) + 20

    def test_format_messages_for_summary_handles_non_string_content(self, compactor):
        """Test handling of non-string message content."""
        messages = [HumanMessage(content=["text", {"type": "image"}])]

        formatted = compactor._format_messages_for_summary(messages)

        # Should convert to string without crashing
        assert "User:" in formatted

    @pytest.mark.asyncio
    async def test_generate_summary_calls_llm(self, compactor):
        """Test _generate_summary calls LLM with correct prompt."""
        messages = [
            HumanMessage(content="What is Python?"),
            AIMessage(content="Python is a programming language."),
        ]

        # Mock the LLM
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "User asked about Python, assistant explained."
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        compactor._llm = mock_llm

        summary = await compactor._generate_summary(messages)

        assert summary == "User asked about Python, assistant explained."
        mock_llm.ainvoke.assert_called_once()

        # Verify the prompt contains the formatted conversation
        call_args = mock_llm.ainvoke.call_args[0][0]
        assert len(call_args) == 1
        assert isinstance(call_args[0], SystemMessage)
        assert "What is Python?" in call_args[0].content
        assert "Python is a programming language" in call_args[0].content

    @pytest.mark.asyncio
    async def test_generate_summary_strips_whitespace(self, compactor):
        """Test _generate_summary strips leading/trailing whitespace."""
        messages = [HumanMessage(content="Test")]

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "  Summary with whitespace  \n"
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        compactor._llm = mock_llm

        summary = await compactor._generate_summary(messages)

        assert summary == "Summary with whitespace"

    @pytest.mark.asyncio
    async def test_generate_summary_handles_non_string_response(self, compactor):
        """Test _generate_summary handles non-string LLM response."""
        messages = [HumanMessage(content="Test")]

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = ["not", "a", "string"]
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        compactor._llm = mock_llm

        summary = await compactor._generate_summary(messages)

        # Should convert to string
        assert isinstance(summary, str)

    @pytest.mark.asyncio
    async def test_compact_below_threshold_no_compaction(self, compactor, mock_memory_service):
        """Test compact() when message count is below threshold."""
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi"),
        ]

        result = await compactor.compact(messages, "conv-123")

        assert result.summary is None
        assert result.recent_messages == messages
        assert result.was_compacted is False
        assert result.original_count == 2
        assert result.compacted_count == 0

        # Should not generate summary or save
        mock_memory_service.get_conversation_summary.assert_not_called()
        mock_memory_service.save_conversation_summary.assert_not_called()

    @pytest.mark.asyncio
    async def test_compact_above_threshold_performs_compaction(
        self, custom_compactor, mock_memory_service
    ):
        """Test compact() performs compaction when above threshold."""
        # Custom compactor: threshold=6, max_turns_verbatim=3
        messages = []
        for i in range(5):  # 10 messages total
            messages.append(HumanMessage(content=f"Message {i}"))
            messages.append(AIMessage(content=f"Response {i}"))

        # Mock LLM
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Summary of messages 0-1."
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        custom_compactor._llm = mock_llm

        result = await custom_compactor.compact(messages, "conv-123")

        assert result.was_compacted is True
        assert result.summary == "Summary of messages 0-1."
        assert result.original_count == 10
        assert result.compacted_count == 4  # First 4 messages summarized
        assert len(result.recent_messages) == 6  # Last 3 turns (6 messages)

        # Verify summary was saved
        mock_memory_service.save_conversation_summary.assert_called_once_with(
            conversation_id="conv-123",
            summary="Summary of messages 0-1.",
            message_count=10,
        )

    @pytest.mark.asyncio
    async def test_compact_combines_with_existing_summary(
        self, custom_compactor, mock_memory_service
    ):
        """Test compact() combines new summary with existing summary."""
        # Setup existing summary
        existing = MagicMock()
        existing.summary = "Earlier conversation about topic A."
        existing.message_count = 5
        mock_memory_service.get_conversation_summary.return_value = existing

        messages = []
        for i in range(5):  # 10 messages
            messages.append(HumanMessage(content=f"Message {i}"))
            messages.append(AIMessage(content=f"Response {i}"))

        # Mock LLM
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Discussion about topic B."
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        custom_compactor._llm = mock_llm

        result = await custom_compactor.compact(messages, "conv-123")

        # Should combine summaries
        assert "Earlier conversation about topic A." in result.summary
        assert "More recently: Discussion about topic B." in result.summary

    @pytest.mark.asyncio
    async def test_compact_truncates_long_combined_summary(
        self, custom_compactor, mock_memory_service
    ):
        """Test compact() truncates combined summary if too long."""
        # Setup long existing summary
        existing = MagicMock()
        existing.summary = "x" * 1000
        existing.message_count = 5
        mock_memory_service.get_conversation_summary.return_value = existing

        messages = []
        for i in range(5):
            messages.append(HumanMessage(content=f"Message {i}"))
            messages.append(AIMessage(content=f"Response {i}"))

        # Mock LLM
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "y" * 1000
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        custom_compactor._llm = mock_llm

        result = await custom_compactor.compact(messages, "conv-123")

        # Combined summary should be truncated to 1500 chars
        assert len(result.summary) == 1500

    @pytest.mark.asyncio
    async def test_compact_handles_llm_failure_gracefully(
        self, custom_compactor, mock_memory_service
    ):
        """Test compact() returns original messages on LLM failure."""
        messages = []
        for i in range(5):
            messages.append(HumanMessage(content=f"Message {i}"))
            messages.append(AIMessage(content=f"Response {i}"))

        # Mock LLM to raise exception
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("API error"))
        custom_compactor._llm = mock_llm

        result = await custom_compactor.compact(messages, "conv-123")

        # Should not crash, return original messages
        assert result.was_compacted is False
        assert result.summary is None
        assert result.recent_messages == messages
        assert result.original_count == 10
        assert result.compacted_count == 0

        # Should not save summary on failure
        mock_memory_service.save_conversation_summary.assert_not_called()

    @pytest.mark.asyncio
    async def test_compact_with_empty_messages(self, compactor):
        """Test compact() handles empty message list."""
        result = await compactor.compact([], "conv-123")

        assert result.summary is None
        assert result.recent_messages == []
        assert result.was_compacted is False
        assert result.original_count == 0
        assert result.compacted_count == 0

    @pytest.mark.asyncio
    async def test_compact_at_exact_threshold(self, compactor):
        """Test compact() behavior exactly at threshold."""
        # Default threshold is 15
        messages = []
        for i in range(7):  # 14 messages
            messages.append(HumanMessage(content=f"Message {i}"))
            messages.append(AIMessage(content=f"Response {i}"))

        result = await compactor.compact(messages, "conv-123")

        # Should not compact when at threshold (needs to exceed)
        assert result.was_compacted is False
        assert result.recent_messages == messages

    @pytest.mark.asyncio
    async def test_compact_one_over_threshold(self, compactor):
        """Test compact() when one message over threshold."""
        # Default threshold is 15, create 16 messages
        messages = []
        for i in range(8):
            messages.append(HumanMessage(content=f"Message {i}"))
            messages.append(AIMessage(content=f"Response {i}"))

        # Mock LLM
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Summary"
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        compactor._llm = mock_llm

        result = await compactor.compact(messages, "conv-123")

        # Should compact when over threshold
        assert result.was_compacted is True

    @pytest.mark.asyncio
    async def test_get_context_with_summary_no_existing_summary(
        self, compactor, mock_memory_service
    ):
        """Test get_context_with_summary when no existing summary."""
        messages = [HumanMessage(content="Hello")]
        mock_memory_service.get_conversation_summary.return_value = None

        summary, returned_messages = await compactor.get_context_with_summary(messages, "conv-123")

        assert summary is None
        assert returned_messages == messages
        mock_memory_service.get_conversation_summary.assert_called_once_with("conv-123")

    @pytest.mark.asyncio
    async def test_get_context_with_summary_with_existing_summary(
        self, compactor, mock_memory_service
    ):
        """Test get_context_with_summary returns existing summary."""
        messages = [HumanMessage(content="Hello")]

        existing = MagicMock()
        existing.summary = "Previous discussion about greetings."
        existing.message_count = 10
        mock_memory_service.get_conversation_summary.return_value = existing

        summary, returned_messages = await compactor.get_context_with_summary(messages, "conv-123")

        assert summary == "Previous discussion about greetings."
        assert returned_messages == messages

    @pytest.mark.asyncio
    async def test_get_context_with_summary_empty_summary(self, compactor, mock_memory_service):
        """Test get_context_with_summary when summary exists but is empty."""
        messages = [HumanMessage(content="Hello")]

        existing = MagicMock()
        existing.summary = ""
        mock_memory_service.get_conversation_summary.return_value = existing

        summary, returned_messages = await compactor.get_context_with_summary(messages, "conv-123")

        # Empty string should be treated as no summary
        assert summary is None
        assert returned_messages == messages

    @pytest.mark.asyncio
    async def test_get_llm_lazy_initialization(self, compactor):
        """Test that LLM is lazily initialized."""
        assert compactor._llm is None

        # Call _get_llm
        llm1 = compactor._get_llm()
        assert compactor._llm is not None

        # Call again, should return same instance
        llm2 = compactor._get_llm()
        assert llm1 is llm2


class TestCompactIfNeededConvenienceFunction:
    """Tests for the compact_if_needed convenience function."""

    @pytest.fixture
    def mock_memory_service(self):
        """Create mock memory service."""
        service = MagicMock()
        service.get_conversation_summary = AsyncMock(return_value=None)
        service.save_conversation_summary = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_compact_if_needed_basic_usage(self, mock_memory_service):
        """Test compact_if_needed convenience function."""
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi"),
        ]

        result = await compact_if_needed(
            messages=messages,
            conversation_id="conv-123",
            memory_service=mock_memory_service,
            config=None,
        )

        assert isinstance(result, CompactionResult)
        assert result.was_compacted is False

    @pytest.mark.asyncio
    async def test_compact_if_needed_with_custom_config(self, mock_memory_service):
        """Test compact_if_needed with custom configuration."""
        config = CompactionConfig(
            max_turns_verbatim=2,
            compaction_threshold=4,
        )

        messages = []
        for i in range(3):  # 6 messages
            messages.append(HumanMessage(content=f"Message {i}"))
            messages.append(AIMessage(content=f"Response {i}"))

        # Need to mock LLM since we're over threshold
        from unittest.mock import patch

        with patch(
            "app.shared.services.memory.compaction_service.LLMFactory.create"
        ) as mock_create:
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "Summary"
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_create.return_value = mock_llm

            result = await compact_if_needed(
                messages=messages,
                conversation_id="conv-123",
                memory_service=mock_memory_service,
                config=config,
            )

            assert result.was_compacted is True


class TestSessionCompactorIntegration:
    """Integration tests for SessionCompactor with realistic scenarios."""

    @pytest.fixture
    def mock_memory_service(self):
        """Create mock memory service."""
        service = MagicMock()
        service.get_conversation_summary = AsyncMock(return_value=None)
        service.save_conversation_summary = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_full_compaction_workflow(self, mock_memory_service):
        """Test complete compaction workflow with realistic conversation."""
        # Create a conversation with 20 messages (10 turns)
        messages = []
        for i in range(10):
            messages.append(HumanMessage(content=f"User question {i}"))
            messages.append(AIMessage(content=f"Assistant answer {i}"))

        config = CompactionConfig(
            max_turns_verbatim=3,  # Keep last 3 turns (6 messages)
            compaction_threshold=10,  # Compact when > 10 messages
        )
        compactor = SessionCompactor(
            memory_service=mock_memory_service,
            config=config,
        )

        # Mock LLM
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "User asked various questions, assistant provided answers."
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        compactor._llm = mock_llm

        result = await compactor.compact(messages, "conv-integration-test")

        # Verify compaction occurred
        assert result.was_compacted is True
        assert result.original_count == 20
        assert result.compacted_count == 14  # First 14 messages summarized
        assert len(result.recent_messages) == 6  # Last 6 messages kept
        assert result.summary == "User asked various questions, assistant provided answers."

        # Verify the right messages were kept
        assert result.recent_messages[0].content == "User question 7"
        assert result.recent_messages[-1].content == "Assistant answer 9"

    @pytest.mark.asyncio
    async def test_iterative_compaction_over_multiple_sessions(self, mock_memory_service):
        """Test compaction over multiple conversation sessions."""
        config = CompactionConfig(
            max_turns_verbatim=2,
            compaction_threshold=4,
        )
        compactor = SessionCompactor(
            memory_service=mock_memory_service,
            config=config,
        )

        # First session: 6 messages
        messages_session1 = []
        for i in range(3):
            messages_session1.append(HumanMessage(content=f"Session 1 - Message {i}"))
            messages_session1.append(AIMessage(content=f"Session 1 - Response {i}"))

        # Mock LLM for first compaction
        mock_llm = MagicMock()
        mock_response1 = MagicMock()
        mock_response1.content = "First session summary."
        mock_llm.ainvoke = AsyncMock(return_value=mock_response1)
        compactor._llm = mock_llm

        result1 = await compactor.compact(messages_session1, "conv-multi-session")

        assert result1.was_compacted is True
        assert "First session summary." in result1.summary

        # Simulate second session: existing summary + new messages
        existing_summary = MagicMock()
        existing_summary.summary = result1.summary
        existing_summary.message_count = 6
        mock_memory_service.get_conversation_summary.return_value = existing_summary

        messages_session2 = []
        for i in range(3):
            messages_session2.append(HumanMessage(content=f"Session 2 - Message {i}"))
            messages_session2.append(AIMessage(content=f"Session 2 - Response {i}"))

        # Mock LLM for second compaction
        mock_response2 = MagicMock()
        mock_response2.content = "Second session summary."
        mock_llm.ainvoke = AsyncMock(return_value=mock_response2)

        result2 = await compactor.compact(messages_session2, "conv-multi-session")

        # Should combine summaries
        assert result2.was_compacted is True
        assert "First session summary." in result2.summary
        assert "More recently: Second session summary." in result2.summary
