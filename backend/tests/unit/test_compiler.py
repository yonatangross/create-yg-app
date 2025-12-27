"""Unit tests for ContextCompiler.

Tests for Issue #7: ContextCompiler with ordered assembly
Tests for Issue #8: Prompt caching with CompiledContext
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.shared.services.context.compaction import (
    CompactionConfig,
    CompiledContext,
    SessionCompactor,
)
from app.shared.services.context.compiler import CompilerResult, ContextCompiler


class TestCompilerResult:
    """Tests for CompilerResult dataclass."""

    def test_compiler_result_basic(self):
        """Test basic CompilerResult creation."""
        messages = [
            SystemMessage(content="System"),
            HumanMessage(content="Hello"),
        ]
        metrics = {
            "total_tokens": 100,
            "compression_ratio": 2.5,
            "total_messages": 2,
        }

        result = CompilerResult(messages=messages, metrics=metrics)

        assert result.messages == messages
        assert result.metrics == metrics
        assert result.total_tokens == 100
        assert result.compression_ratio == 2.5

    def test_compiler_result_defaults(self):
        """Test CompilerResult with missing metrics."""
        result = CompilerResult(messages=[], metrics={})

        assert result.total_tokens == 0
        assert result.compression_ratio == 1.0


class TestContextCompiler:
    """Tests for ContextCompiler."""

    @pytest.fixture
    def compactor(self):
        """Create SessionCompactor with default config."""
        return SessionCompactor()

    @pytest.fixture
    def compiler(self, compactor):
        """Create ContextCompiler with compactor."""
        return ContextCompiler(compactor=compactor)

    def test_compiler_initialization_default(self):
        """Test compiler initializes with default compactor."""
        compiler = ContextCompiler()
        assert compiler.compactor is not None
        assert isinstance(compiler.compactor, SessionCompactor)

    def test_compiler_initialization_custom(self, compactor):
        """Test compiler initializes with custom compactor."""
        compiler = ContextCompiler(compactor=compactor)
        assert compiler.compactor is compactor

    @pytest.mark.asyncio
    async def test_compile_validates_system_prompt(self, compiler):
        """Test that empty system_prompt raises ValueError."""
        with pytest.raises(ValueError, match="system_prompt cannot be empty"):
            await compiler.compile(
                system_prompt="",
                history=[],
                current_input="Hello",
            )

        with pytest.raises(ValueError, match="system_prompt cannot be empty"):
            await compiler.compile(
                system_prompt="   ",  # Whitespace only
                history=[],
                current_input="Hello",
            )

    @pytest.mark.asyncio
    async def test_compile_validates_current_input(self, compiler):
        """Test that empty current_input raises ValueError."""
        with pytest.raises(ValueError, match="current_input cannot be empty"):
            await compiler.compile(
                system_prompt="You are a helpful assistant.",
                history=[],
                current_input="",
            )

        with pytest.raises(ValueError, match="current_input cannot be empty"):
            await compiler.compile(
                system_prompt="You are a helpful assistant.",
                history=[],
                current_input="   ",  # Whitespace only
            )

    @pytest.mark.asyncio
    async def test_compile_simple_no_history(self, compiler):
        """Test simple compilation without history."""
        result = await compiler.compile(
            system_prompt="You are a helpful assistant.",
            history=[],
            current_input="What is AI?",
        )

        # Should have: system prompt + current input
        assert len(result.messages) == 2
        assert isinstance(result.messages[0], SystemMessage)
        assert result.messages[0].content == "You are a helpful assistant."
        assert isinstance(result.messages[1], HumanMessage)
        assert result.messages[1].content == "What is AI?"

        # Check metrics
        assert result.metrics["original_history_count"] == 0
        assert result.metrics["total_messages"] == 2
        assert result.metrics["has_proactive_context"] is False

    @pytest.mark.asyncio
    async def test_compile_with_proactive_context(self, compiler):
        """Test compilation with proactive memory context."""
        result = await compiler.compile(
            system_prompt="You are a helpful assistant.",
            history=[],
            current_input="What's my preference?",
            proactive_context="User prefers dark mode and TypeScript.",
        )

        # Should have: system prompt + proactive context + current input
        assert len(result.messages) == 3
        assert isinstance(result.messages[0], SystemMessage)
        assert result.messages[0].content == "You are a helpful assistant."

        assert isinstance(result.messages[1], SystemMessage)
        assert "Relevant Context from Memory" in result.messages[1].content
        assert "dark mode" in result.messages[1].content

        assert isinstance(result.messages[2], HumanMessage)
        assert result.messages[2].content == "What's my preference?"

        # Check metrics
        assert result.metrics["has_proactive_context"] is True

    @pytest.mark.asyncio
    async def test_compile_with_short_history_no_compaction(self, compiler):
        """Test compilation with short history (no compaction needed)."""
        history = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
            HumanMessage(content="How are you?"),
            AIMessage(content="I'm doing well!"),
        ]

        result = await compiler.compile(
            system_prompt="You are a helpful assistant.",
            history=history,
            current_input="What did I ask first?",
        )

        # Should have: system prompt + history (4) + current input
        assert len(result.messages) == 6
        assert isinstance(result.messages[0], SystemMessage)
        # Messages 1-4 are history
        assert result.messages[1].content == "Hello"
        assert result.messages[2].content == "Hi there!"
        # Last is current input
        assert isinstance(result.messages[-1], HumanMessage)
        assert result.messages[-1].content == "What did I ask first?"

        # Check metrics
        assert result.metrics["original_history_count"] == 4
        assert result.metrics["compacted_history_count"] == 4
        assert result.metrics["has_summary"] is False

    @pytest.mark.asyncio
    async def test_compile_with_long_history_triggers_compaction(self):
        """Test compilation with long history triggers compaction."""
        # Custom compactor with low threshold
        config = CompactionConfig(
            max_turns_full=2,
            summarize_after=4,
            summary_max_tokens=200,
        )
        compactor = SessionCompactor(config)
        compiler = ContextCompiler(compactor)

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

        # Mock the LLM for summarization
        with patch("app.shared.services.context.compaction.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "User asked about messages 1-2."
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_get_llm.return_value = mock_llm

            result = await compiler.compile(
                system_prompt="You are a helpful assistant.",
                history=history,
                current_input="What did I ask?",
            )

            # Should have:
            # - System prompt (1)
            # - Summary prefix (1)
            # - Recent messages (last 2 turns = 4 messages)
            # - Current input (1)
            # Total: 7
            assert len(result.messages) >= 6  # At least these

            # First message is system prompt
            assert isinstance(result.messages[0], SystemMessage)
            assert result.messages[0].content == "You are a helpful assistant."

            # Should have summary in prefix
            has_summary = any(
                isinstance(msg, SystemMessage) and "Previous conversation summary" in msg.content
                for msg in result.messages
            )
            assert has_summary

            # Last message is current input
            assert isinstance(result.messages[-1], HumanMessage)
            assert result.messages[-1].content == "What did I ask?"

            # Check metrics
            assert result.metrics["has_summary"] is True
            assert result.metrics["compression_ratio"] > 1.0

    @pytest.mark.asyncio
    async def test_compile_preserves_tool_calls_in_history(self):
        """Test that tool calls are preserved during compaction."""
        config = CompactionConfig(
            max_turns_full=1,
            summarize_after=3,
            preserve_tool_calls=True,
        )
        compactor = SessionCompactor(config)
        compiler = ContextCompiler(compactor)

        history = [
            HumanMessage(content="Search for cats"),
            AIMessage(
                content="Searching...",
                tool_calls=[{"name": "search", "args": {"query": "cats"}, "id": "call_1"}],
            ),
            ToolMessage(content="Found cats", tool_call_id="call_1"),
            HumanMessage(content="Thanks"),
            AIMessage(content="You're welcome"),
        ]

        with patch("app.shared.services.context.compaction.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "User searched for cats."
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_get_llm.return_value = mock_llm

            result = await compiler.compile(
                system_prompt="You are a helpful assistant.",
                history=history,
                current_input="What did I search for?",
            )

            # Tool messages should be preserved
            has_tool_call = any(
                hasattr(msg, "tool_calls") and msg.tool_calls for msg in result.messages
            )
            has_tool_message = any(isinstance(msg, ToolMessage) for msg in result.messages)

            assert has_tool_call or has_tool_message

    @pytest.mark.asyncio
    async def test_compile_message_ordering(self, compiler):
        """Test that messages are in correct order."""
        history = [
            HumanMessage(content="First question"),
            AIMessage(content="First answer"),
        ]

        result = await compiler.compile(
            system_prompt="You are a helpful assistant.",
            history=history,
            current_input="Second question",
            proactive_context="User likes Python.",
        )

        # Verify order:
        # 1. System prompt
        assert isinstance(result.messages[0], SystemMessage)
        assert result.messages[0].content == "You are a helpful assistant."

        # 2. Proactive context
        assert isinstance(result.messages[1], SystemMessage)
        assert "Python" in result.messages[1].content

        # 3. History
        assert result.messages[2].content == "First question"
        assert result.messages[3].content == "First answer"

        # 4. Current input (last)
        assert isinstance(result.messages[-1], HumanMessage)
        assert result.messages[-1].content == "Second question"

    @pytest.mark.asyncio
    async def test_compile_simple_convenience_method(self, compiler):
        """Test compile_simple convenience method."""
        result = await compiler.compile_simple(
            system_prompt="You are a helpful assistant.",
            current_input="What is AI?",
        )

        # Should have: system prompt + current input
        assert len(result.messages) == 2
        assert isinstance(result.messages[0], SystemMessage)
        assert isinstance(result.messages[1], HumanMessage)

        # Metrics should show no history or proactive context
        assert result.metrics["original_history_count"] == 0
        assert result.metrics["has_proactive_context"] is False

    @pytest.mark.asyncio
    async def test_compile_metrics_accuracy(self):
        """Test that compilation metrics are accurate."""
        config = CompactionConfig(max_turns_full=2, summarize_after=4)
        compactor = SessionCompactor(config)
        compiler = ContextCompiler(compactor)

        history = [HumanMessage(content=f"Message {i}") for i in range(10)]

        with patch("app.shared.services.context.compaction.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "Summary of older messages."
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_get_llm.return_value = mock_llm

            result = await compiler.compile(
                system_prompt="System",
                history=history,
                current_input="Current",
            )

            # Verify metrics
            assert result.metrics["original_history_count"] == 10
            assert result.metrics["total_messages"] == len(result.messages)
            assert result.metrics["total_tokens"] > 0
            assert isinstance(result.metrics["compression_ratio"], float)

    @pytest.mark.asyncio
    async def test_compile_ignores_empty_proactive_context(self, compiler):
        """Test that empty/whitespace proactive_context is ignored."""
        result = await compiler.compile(
            system_prompt="You are a helpful assistant.",
            history=[],
            current_input="Hello",
            proactive_context="   ",  # Whitespace only
        )

        # Should not add proactive context message
        assert len(result.messages) == 2
        assert result.metrics["has_proactive_context"] is False


class TestCompiledContextPromptCaching:
    """Tests for Issue #8: Prompt caching with CompiledContext."""

    def test_to_messages_with_cache_empty_prefix(self):
        """Test caching with empty prefix."""
        ctx = CompiledContext(
            prefix=[],
            messages=[HumanMessage(content="Hello")],
        )

        result = ctx.to_messages_with_cache()

        # Should have only messages, no cache headers
        assert len(result) == 1
        assert result[0].content == "Hello"

    def test_to_messages_with_cache_single_prefix(self):
        """Test caching with single prefix message."""
        ctx = CompiledContext(
            prefix=[SystemMessage(content="You are a helpful assistant.")],
            messages=[HumanMessage(content="Hello")],
        )

        result = ctx.to_messages_with_cache()

        # Should have 2 messages total
        assert len(result) == 2

        # First message (prefix) should have cache_control
        assert isinstance(result[0], SystemMessage)
        assert "cache_control" in result[0].additional_kwargs
        assert result[0].additional_kwargs["cache_control"] == {"type": "ephemeral"}

        # Second message (dynamic) should not have cache_control
        assert isinstance(result[1], HumanMessage)
        assert "cache_control" not in result[1].additional_kwargs

    def test_to_messages_with_cache_multiple_prefix(self):
        """Test caching with multiple prefix messages."""
        ctx = CompiledContext(
            prefix=[
                SystemMessage(content="You are a helpful assistant."),
                SystemMessage(content="Previous conversation summary: User asked about AI."),
            ],
            messages=[
                HumanMessage(content="What else?"),
                AIMessage(content="More info."),
            ],
        )

        result = ctx.to_messages_with_cache()

        # Should have 4 messages total
        assert len(result) == 4

        # First prefix message should NOT have cache_control
        assert isinstance(result[0], SystemMessage)
        assert "cache_control" not in result[0].additional_kwargs

        # Last prefix message SHOULD have cache_control
        assert isinstance(result[1], SystemMessage)
        assert "cache_control" in result[1].additional_kwargs
        assert result[1].additional_kwargs["cache_control"] == {"type": "ephemeral"}

        # Dynamic messages should not have cache_control
        assert "cache_control" not in result[2].additional_kwargs
        assert "cache_control" not in result[3].additional_kwargs

    def test_to_messages_with_cache_preserves_original_messages(self):
        """Test that original messages are not modified."""
        original_prefix = SystemMessage(content="System prompt")
        original_message = HumanMessage(content="Hello")

        ctx = CompiledContext(
            prefix=[original_prefix],
            messages=[original_message],
        )

        result = ctx.to_messages_with_cache()

        # Original messages should not be modified
        assert "cache_control" not in original_prefix.additional_kwargs
        assert "cache_control" not in original_message.additional_kwargs

        # Result should have cache_control on copied message
        assert "cache_control" in result[0].additional_kwargs

    def test_to_messages_with_cache_preserves_existing_additional_kwargs(self):
        """Test that existing additional_kwargs are preserved."""
        prefix_msg = SystemMessage(
            content="System prompt",
            additional_kwargs={"existing_key": "existing_value"},
        )

        ctx = CompiledContext(
            prefix=[prefix_msg],
            messages=[],
        )

        result = ctx.to_messages_with_cache()

        # Should preserve existing additional_kwargs
        assert result[0].additional_kwargs["existing_key"] == "existing_value"
        assert result[0].additional_kwargs["cache_control"] == {"type": "ephemeral"}

    def test_to_messages_with_cache_only_prefix_no_messages(self):
        """Test caching with only prefix, no dynamic messages."""
        ctx = CompiledContext(
            prefix=[
                SystemMessage(content="System prompt"),
                SystemMessage(content="Summary"),
            ],
            messages=[],
        )

        result = ctx.to_messages_with_cache()

        # Should have 2 messages
        assert len(result) == 2

        # Last prefix should have cache_control
        assert "cache_control" in result[1].additional_kwargs

    def test_to_messages_with_cache_integration_with_compiler(self):
        """Test prompt caching integration with compiled context."""
        # Simulate a compiled context from compactor
        ctx = CompiledContext(
            prefix=[
                SystemMessage(content="You are a helpful assistant."),
                SystemMessage(content="Previous conversation summary: User asked about AI."),
            ],
            messages=[
                HumanMessage(content="Tell me more"),
                AIMessage(content="AI is fascinating"),
            ],
            summary="User asked about AI.",
            original_count=20,
        )

        result = ctx.to_messages_with_cache()

        # Verify structure
        assert len(result) == 4

        # Prefix messages
        assert isinstance(result[0], SystemMessage)
        assert "cache_control" not in result[0].additional_kwargs

        assert isinstance(result[1], SystemMessage)
        assert result[1].additional_kwargs["cache_control"] == {"type": "ephemeral"}

        # Dynamic messages (no cache)
        assert isinstance(result[2], HumanMessage)
        assert isinstance(result[3], AIMessage)
        assert "cache_control" not in result[2].additional_kwargs
        assert "cache_control" not in result[3].additional_kwargs
