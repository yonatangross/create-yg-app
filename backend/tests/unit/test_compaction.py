"""Unit tests for conversation compaction with summarization."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import ValidationError

from app.shared.services.context.compaction import (
    CompactionConfig,
    CompiledContext,
    SessionCompactor,
)


class TestCompactionConfig:
    """Tests for CompactionConfig validation."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CompactionConfig()

        assert config.max_turns_full == 5
        assert config.summarize_after == 10
        assert config.summary_max_tokens == 500
        assert config.token_budget == 6000
        assert config.preserve_tool_calls is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = CompactionConfig(
            max_turns_full=10,
            summarize_after=20,
            summary_max_tokens=1000,
            token_budget=10000,
            preserve_tool_calls=False,
        )

        assert config.max_turns_full == 10
        assert config.summarize_after == 20
        assert config.summary_max_tokens == 1000
        assert config.token_budget == 10000
        assert config.preserve_tool_calls is False

    def test_token_budget_validation_fails_when_too_small(self):
        """Test that token budget must be > 2x summary_max_tokens."""
        with pytest.raises(ValidationError, match="token_budget must exceed"):
            CompactionConfig(
                summary_max_tokens=500,
                token_budget=1000,  # Must be > 1000 (2x500)
            )

    def test_token_budget_validation_passes_when_sufficient(self):
        """Test that token budget validation passes when sufficient."""
        config = CompactionConfig(
            summary_max_tokens=500,
            token_budget=1001,  # Just above minimum
        )
        assert config.token_budget == 1001


class TestCompiledContext:
    """Tests for CompiledContext dataclass."""

    def test_empty_compiled_context(self):
        """Test empty compiled context."""
        ctx = CompiledContext()

        assert ctx.prefix == []
        assert ctx.messages == []
        assert ctx.summary is None
        assert ctx.original_count == 0

    def test_compression_ratio_calculation(self):
        """Test compression ratio calculation."""
        ctx = CompiledContext(
            prefix=[SystemMessage(content="Summary")],
            messages=[HumanMessage(content="Hello"), AIMessage(content="Hi")],
            original_count=20,
        )

        # Original: 20, After: 3 (1 prefix + 2 messages)
        # Ratio: 20/3 ≈ 6.67
        assert abs(ctx.compression_ratio - 6.67) < 0.01

    def test_compression_ratio_no_compression(self):
        """Test compression ratio when no compression occurred."""
        ctx = CompiledContext(
            prefix=[],
            messages=[HumanMessage(content="Hello"), AIMessage(content="Hi")],
            original_count=2,
        )

        # Original: 2, After: 2
        # Ratio: 2/2 = 1.0
        assert ctx.compression_ratio == 1.0

    def test_compression_ratio_handles_zero_compiled(self):
        """Test compression ratio when compiled is empty (edge case)."""
        ctx = CompiledContext(
            prefix=[],
            messages=[],
            original_count=10,
        )

        # Original: 10, After: 0 -> max(0, 1) = 1
        # Ratio: 10/1 = 10.0
        assert ctx.compression_ratio == 10.0


class TestSessionCompactor:
    """Tests for SessionCompactor."""

    @pytest.fixture
    def compactor(self):
        """Create SessionCompactor with default config."""
        return SessionCompactor()

    @pytest.fixture
    def custom_compactor(self):
        """Create SessionCompactor with custom config."""
        config = CompactionConfig(
            max_turns_full=3,
            summarize_after=6,
            summary_max_tokens=200,
        )
        return SessionCompactor(config)

    def test_is_tool_related_detects_tool_message(self, compactor):
        """Test tool message detection."""
        tool_msg = ToolMessage(
            content="Result",
            tool_call_id="call_123",
        )
        assert compactor._is_tool_related(tool_msg) is True

    def test_is_tool_related_detects_ai_message_with_tool_calls(self, compactor):
        """Test AI message with tool_calls attribute."""
        ai_msg = AIMessage(content="Calling tool")
        ai_msg.tool_calls = [{"name": "search", "args": {"query": "test"}}]
        assert compactor._is_tool_related(ai_msg) is True

    def test_is_tool_related_detects_additional_kwargs(self, compactor):
        """Test message with tool_calls in additional_kwargs."""
        ai_msg = AIMessage(
            content="Calling tool",
            additional_kwargs={"tool_calls": [{"function": {"name": "search"}}]},
        )
        assert compactor._is_tool_related(ai_msg) is True

    def test_is_tool_related_returns_false_for_regular_message(self, compactor):
        """Test regular messages are not tool-related."""
        human_msg = HumanMessage(content="Hello")
        ai_msg = AIMessage(content="Hi there")

        assert compactor._is_tool_related(human_msg) is False
        assert compactor._is_tool_related(ai_msg) is False

    def test_format_messages_basic(self, compactor):
        """Test message formatting for summarization."""
        messages = [
            HumanMessage(content="What is AI?"),
            AIMessage(content="AI is artificial intelligence."),
        ]

        formatted = compactor._format_messages(messages)

        assert "User: What is AI?" in formatted
        assert "Assistant: AI is artificial intelligence." in formatted

    def test_format_messages_truncates_long_content(self, compactor):
        """Test that long messages are truncated."""
        long_content = "x" * 1000
        messages = [HumanMessage(content=long_content)]

        formatted = compactor._format_messages(messages)

        # Should be truncated to 500 chars + "..."
        assert len(formatted) < len(long_content) + 10
        assert "..." in formatted

    def test_merge_chronologically_basic(self, compactor):
        """Test merging regular and tool messages."""
        regular = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi"),
        ]
        tool = [
            ToolMessage(content="Result", tool_call_id="call_1"),
        ]

        merged = compactor._merge_chronologically(regular, tool)

        assert len(merged) == 3
        assert merged[0].content == "Hello"
        assert merged[1].content == "Hi"
        assert merged[2].content == "Result"

    @pytest.mark.asyncio
    async def test_compact_no_summarization_under_threshold(self, compactor):
        """Test no compaction when under threshold."""
        history = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi"),
            HumanMessage(content="How are you?"),
            AIMessage(content="I'm good!"),
        ]

        result = await compactor.compact(history)

        assert result.prefix == []
        assert result.messages == history
        assert result.summary is None
        assert result.original_count == 4
        assert result.compression_ratio == 1.0

    @pytest.mark.asyncio
    async def test_compact_with_summarization_over_threshold(self, custom_compactor):
        """Test compaction with summarization when over threshold."""
        # Custom compactor: summarize_after=6, max_turns_full=3
        history = [
            HumanMessage(content="Message 1"),
            AIMessage(content="Response 1"),
            HumanMessage(content="Message 2"),
            AIMessage(content="Response 2"),
            HumanMessage(content="Message 3"),
            AIMessage(content="Response 3"),
            HumanMessage(content="Message 4"),
            AIMessage(content="Response 4"),
        ]

        # Mock the LLM to return a summary
        with patch("app.shared.services.context.compaction.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "Previous discussion about messages 1-2."
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_get_llm.return_value = mock_llm

            result = await custom_compactor.compact(history)

            # Should have prefix with summary
            assert len(result.prefix) == 1
            assert isinstance(result.prefix[0], SystemMessage)
            assert "Previous discussion" in result.prefix[0].content

            # Recent messages (last 3 turns = 6 messages) should be preserved
            assert len(result.messages) == 6

            # Summary should be set
            assert result.summary == "Previous discussion about messages 1-2."

            # Original count should be preserved
            assert result.original_count == 8

            # Compression ratio should be > 1
            assert result.compression_ratio > 1.0

    @pytest.mark.asyncio
    async def test_compact_preserves_tool_calls(self, custom_compactor):
        """Test that tool calls are preserved even when old."""
        history = [
            HumanMessage(content="Search for cats"),
            AIMessage(
                content="Searching...",
                tool_calls=[{"name": "search", "args": {"query": "cats"}, "id": "call_1"}],
            ),
            ToolMessage(content="Found cats", tool_call_id="call_1"),
            HumanMessage(content="Message 2"),
            AIMessage(content="Response 2"),
            HumanMessage(content="Message 3"),
            AIMessage(content="Response 3"),
            HumanMessage(content="Message 4"),
            AIMessage(content="Response 4"),
        ]

        # Mock the LLM
        with patch("app.shared.services.context.compaction.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "User searched for cats."
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_get_llm.return_value = mock_llm

            result = await custom_compactor.compact(history)

            # Tool messages should be preserved
            has_tool_call = any(
                hasattr(msg, "tool_calls") and msg.tool_calls for msg in result.messages
            )
            has_tool_message = any(isinstance(msg, ToolMessage) for msg in result.messages)

            assert has_tool_call or has_tool_message

    @pytest.mark.asyncio
    async def test_summarize_success(self, compactor):
        """Test successful summarization."""
        messages = [
            HumanMessage(content="What is AI?"),
            AIMessage(content="AI is artificial intelligence."),
        ]

        with patch("app.shared.services.context.compaction.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "User asked about AI, assistant explained."
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_get_llm.return_value = mock_llm

            summary = await compactor._summarize(messages)

            assert summary == "User asked about AI, assistant explained."

    @pytest.mark.asyncio
    async def test_summarize_truncates_long_summary(self, compactor):
        """Test that very long summaries are truncated."""
        messages = [HumanMessage(content="Test")]

        # Generate summary longer than max_tokens * 4
        long_summary = "x" * (compactor.config.summary_max_tokens * 4 + 100)

        with patch("app.shared.services.context.compaction.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = long_summary
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_get_llm.return_value = mock_llm

            summary = await compactor._summarize(messages)

            # Should be truncated
            assert summary is not None
            assert len(summary) < len(long_summary)
            assert summary.endswith("...")

    @pytest.mark.asyncio
    async def test_summarize_handles_llm_failure(self, compactor):
        """Test graceful handling of LLM failures."""
        messages = [HumanMessage(content="Test")]

        with patch("app.shared.services.context.compaction.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(side_effect=Exception("API Error"))
            mock_get_llm.return_value = mock_llm

            summary = await compactor._summarize(messages)

            # Should return None on failure
            assert summary is None

    @pytest.mark.asyncio
    async def test_compact_handles_empty_history(self, compactor):
        """Test compaction with empty history."""
        history = []

        result = await compactor.compact(history)

        assert result.prefix == []
        assert result.messages == []
        assert result.summary is None
        assert result.original_count == 0

    @pytest.mark.asyncio
    async def test_compact_separates_tool_and_regular_messages(self):
        """Test that tool and regular messages are properly separated."""
        history = [
            HumanMessage(content="Hello"),
            AIMessage(
                content="Hi",
                tool_calls=[{"name": "test", "args": {}, "id": "call_1"}],
            ),
            ToolMessage(content="Result", tool_call_id="call_1"),
            HumanMessage(content="Thanks"),
            AIMessage(content="Welcome"),
        ]

        # Use custom compactor with low threshold
        config = CompactionConfig(summarize_after=3, max_turns_full=1)
        compactor_custom = SessionCompactor(config)

        with patch("app.shared.services.context.compaction.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "Initial greeting."
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_get_llm.return_value = mock_llm

            result = await compactor_custom.compact(history)

            # Tool-related messages should be preserved
            tool_count = sum(
                1
                for msg in result.messages
                if isinstance(msg, ToolMessage) or (hasattr(msg, "tool_calls") and msg.tool_calls)
            )
            assert tool_count >= 2  # AI with tool_calls + ToolMessage

    @pytest.mark.asyncio
    async def test_compact_with_non_string_content(self, compactor):
        """Test handling of messages with non-string content."""
        history = [
            HumanMessage(content=["text", {"type": "image"}]),
            AIMessage(content="Response"),
        ]

        result = await compactor.compact(history)

        # Should not crash, should handle gracefully
        assert result.original_count == 2


class TestSessionCompactorIntegration:
    """Integration tests for SessionCompactor."""

    @pytest.mark.asyncio
    async def test_full_compaction_workflow(self):
        """Test complete compaction workflow with real scenario."""
        # Simulate a long conversation
        history = []
        for i in range(15):
            history.append(HumanMessage(content=f"User message {i}"))
            history.append(AIMessage(content=f"Assistant response {i}"))

        # Add some tool calls
        history[10] = AIMessage(
            content="Using search tool",
            tool_calls=[{"name": "search", "args": {"query": "test"}, "id": "call_1"}],
        )
        history.insert(11, ToolMessage(content="Search results", tool_call_id="call_1"))

        config = CompactionConfig(
            max_turns_full=5,
            summarize_after=10,
            preserve_tool_calls=True,
        )
        compactor = SessionCompactor(config)

        with patch("app.shared.services.context.compaction.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "Earlier conversation about messages 0-4."
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_get_llm.return_value = mock_llm

            result = await compactor.compact(history)

            # Should have summary in prefix
            assert len(result.prefix) >= 1
            assert isinstance(result.prefix[0], SystemMessage)

            # Should have recent messages + tool calls
            assert len(result.messages) > 0

            # Should have reduced message count
            assert len(result.prefix) + len(result.messages) < len(history)

            # Compression ratio should be > 1
            assert result.compression_ratio > 1.0

            # Tool messages should be preserved
            has_tool = any(
                isinstance(msg, ToolMessage) or (hasattr(msg, "tool_calls") and msg.tool_calls)
                for msg in result.messages
            )
            assert has_tool is True
