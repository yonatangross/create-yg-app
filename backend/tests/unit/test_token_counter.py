"""Tests for token counter utilities.

Tests accurate token counting using tiktoken for context management.
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.shared.services.context import (
    count_message_tokens,
    count_messages_tokens,
    count_tokens,
    get_token_budget_messages,
    truncate_to_tokens,
)


class TestCountTokens:
    """Test basic token counting."""

    def test_empty_string(self):
        """Empty string should have 0 tokens."""
        assert count_tokens("") == 0

    def test_simple_text(self):
        """Simple text should count tokens accurately."""
        # "Hello world" is typically 2 tokens in cl100k_base
        result = count_tokens("Hello world")
        assert result == 2

    def test_longer_text(self):
        """Longer text should count more tokens."""
        text = "The quick brown fox jumps over the lazy dog"
        result = count_tokens(text)
        # This phrase is typically ~9 tokens
        assert 8 <= result <= 10

    def test_special_characters(self):
        """Special characters should be counted."""
        text = "Hello! How are you? I'm fine, thanks."
        result = count_tokens(text)
        assert result > 0

    def test_unicode_text(self):
        """Unicode characters should be counted."""
        text = "Hello 世界 🌍"
        result = count_tokens(text)
        assert result > 0

    def test_code_text(self):
        """Code should be counted accurately."""
        code = "def hello():\n    return 'world'"
        result = count_tokens(code)
        assert result > 5


class TestCountMessageTokens:
    """Test message token counting with overhead."""

    def test_human_message(self):
        """Human message should include overhead."""
        msg = HumanMessage(content="Hello")
        result = count_message_tokens(msg)
        # "Hello" is 1 token + 4 overhead = 5
        assert result == 5

    def test_ai_message(self):
        """AI message should include overhead."""
        msg = AIMessage(content="Hi there!")
        result = count_message_tokens(msg)
        # "Hi there!" is ~3 tokens + 4 overhead
        assert result >= 7

    def test_system_message(self):
        """System message should include overhead."""
        msg = SystemMessage(content="You are a helpful assistant.")
        result = count_message_tokens(msg)
        # Should be content tokens + 4 overhead
        content_tokens = count_tokens("You are a helpful assistant.")
        assert result == content_tokens + 4

    def test_tool_message(self):
        """Tool message should include overhead."""
        msg = ToolMessage(content="Result: 42", tool_call_id="call_123")
        result = count_message_tokens(msg)
        # Should be content tokens + 4 overhead
        content_tokens = count_tokens("Result: 42")
        assert result == content_tokens + 4

    def test_empty_message(self):
        """Empty message should still have overhead."""
        msg = HumanMessage(content="")
        result = count_message_tokens(msg)
        assert result == 4  # Just the overhead

    def test_long_message(self):
        """Long message should count accurately."""
        long_text = "This is a much longer message that contains many words. " * 10
        msg = HumanMessage(content=long_text)
        result = count_message_tokens(msg)
        # Should be significantly more than overhead
        assert result > 50


class TestCountMessagesTokens:
    """Test counting tokens across multiple messages."""

    def test_empty_list(self):
        """Empty message list should have 0 tokens."""
        assert count_messages_tokens([]) == 0

    def test_single_message(self):
        """Single message should count correctly."""
        messages = [HumanMessage(content="Hello")]
        result = count_messages_tokens(messages)
        assert result == count_message_tokens(messages[0])

    def test_multiple_messages(self):
        """Multiple messages should sum correctly."""
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
            HumanMessage(content="How are you?"),
        ]
        result = count_messages_tokens(messages)
        expected = sum(count_message_tokens(m) for m in messages)
        assert result == expected

    def test_conversation(self):
        """Realistic conversation should count accurately."""
        messages = [
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content="What is 2+2?"),
            AIMessage(content="2+2 equals 4."),
            HumanMessage(content="Thanks!"),
            AIMessage(content="You're welcome!"),
        ]
        result = count_messages_tokens(messages)
        # Should be sum of all individual counts
        assert result == sum(count_message_tokens(m) for m in messages)


class TestTruncateToTokens:
    """Test text truncation to token limits."""

    def test_no_truncation_needed(self):
        """Text within limit should not be truncated."""
        text = "Hello world"
        result = truncate_to_tokens(text, max_tokens=10)
        assert result == text

    def test_exact_limit(self):
        """Text at exact limit should not be truncated."""
        text = "Hello world"
        token_count = count_tokens(text)
        result = truncate_to_tokens(text, max_tokens=token_count)
        assert result == text

    def test_truncation_needed(self):
        """Text over limit should be truncated."""
        text = "The quick brown fox jumps over the lazy dog"
        result = truncate_to_tokens(text, max_tokens=5)
        # Should be truncated
        assert len(result) < len(text)
        # Should not exceed token limit
        assert count_tokens(result) <= 5

    def test_truncate_to_zero(self):
        """Truncating to 0 tokens should return empty string."""
        text = "Hello world"
        result = truncate_to_tokens(text, max_tokens=0)
        assert result == ""

    def test_truncate_long_text(self):
        """Truncating long text should work correctly."""
        text = "This is a very long text. " * 100
        result = truncate_to_tokens(text, max_tokens=50)
        # Should not exceed limit
        assert count_tokens(result) <= 50
        # Should be significantly shorter
        assert len(result) < len(text)

    def test_truncate_unicode(self):
        """Truncating unicode text should work correctly."""
        text = "Hello 世界! " * 20
        result = truncate_to_tokens(text, max_tokens=10)
        # Should not exceed limit
        assert count_tokens(result) <= 10
        # Should be valid string
        assert isinstance(result, str)


class TestGetTokenBudgetMessages:
    """Test filtering messages to fit token budget."""

    def test_empty_messages(self):
        """Empty message list should return empty list."""
        result = get_token_budget_messages([], token_budget=100)
        assert result == []

    def test_all_fit_within_budget(self):
        """All messages within budget should be returned."""
        messages = [
            HumanMessage(content="Hi"),
            AIMessage(content="Hello"),
        ]
        total_tokens = count_messages_tokens(messages)
        result = get_token_budget_messages(messages, token_budget=total_tokens + 10)
        assert result == messages

    def test_keep_most_recent(self):
        """Should keep most recent messages when over budget."""
        messages = [
            HumanMessage(content="First message"),
            HumanMessage(content="Second message"),
            HumanMessage(content="Third message"),
        ]
        # Budget for only 1-2 messages
        result = get_token_budget_messages(messages, token_budget=15)
        # Should keep recent messages
        assert len(result) < len(messages)
        # Should include most recent message
        assert result[-1] == messages[-1]

    def test_single_message_over_budget(self):
        """Single message over budget should return empty list."""
        messages = [HumanMessage(content="Very long message" * 50)]
        result = get_token_budget_messages(messages, token_budget=5)
        assert result == []

    def test_preserves_order(self):
        """Should preserve message order."""
        messages = [
            HumanMessage(content="1"),
            HumanMessage(content="2"),
            HumanMessage(content="3"),
            HumanMessage(content="4"),
        ]
        result = get_token_budget_messages(messages, token_budget=20)
        # Should maintain order
        for i in range(len(result) - 1):
            assert messages.index(result[i]) < messages.index(result[i + 1])

    def test_exact_budget_fit(self):
        """Messages that exactly fit budget should all be returned."""
        messages = [
            HumanMessage(content="Hi"),
            HumanMessage(content="Hello"),
        ]
        total_tokens = count_messages_tokens(messages)
        result = get_token_budget_messages(messages, token_budget=total_tokens)
        assert result == messages

    def test_conversation_budget(self):
        """Realistic conversation should respect budget."""
        messages = [
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content="What is the capital of France?"),
            AIMessage(content="The capital of France is Paris."),
            HumanMessage(content="What about Germany?"),
            AIMessage(content="The capital of Germany is Berlin."),
            HumanMessage(content="Thanks!"),
        ]
        # Budget for roughly 3 messages
        result = get_token_budget_messages(messages, token_budget=50)
        # Should have some messages
        assert len(result) > 0
        # Should be less than all messages
        assert len(result) <= len(messages)
        # Should not exceed budget
        assert count_messages_tokens(result) <= 50
        # Should include most recent
        assert result[-1] == messages[-1]

    def test_zero_budget(self):
        """Zero budget should return empty list."""
        messages = [HumanMessage(content="Hello")]
        result = get_token_budget_messages(messages, token_budget=0)
        assert result == []


class TestIntegration:
    """Integration tests for token counter utilities."""

    def test_budget_workflow(self):
        """Test typical workflow of managing message budget."""
        # Start with conversation
        messages = [
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content="Tell me about Python"),
            AIMessage(content="Python is a high-level programming language..."),
            HumanMessage(content="What about its history?"),
            AIMessage(content="Python was created by Guido van Rossum..."),
            HumanMessage(content="Cool, thanks!"),
        ]

        # Count total tokens
        total = count_messages_tokens(messages)
        assert total > 0

        # Apply budget
        budget = total // 2  # 50% budget
        filtered = get_token_budget_messages(messages, token_budget=budget)

        # Verify filtered messages respect budget
        filtered_total = count_messages_tokens(filtered)
        assert filtered_total <= budget

        # Verify most recent messages are kept
        assert filtered[-1] == messages[-1]

    def test_truncate_and_count(self):
        """Test truncating text and verifying token count."""
        long_text = "This is a very long piece of text. " * 100
        original_count = count_tokens(long_text)

        # Truncate to half
        truncated = truncate_to_tokens(long_text, max_tokens=original_count // 2)
        truncated_count = count_tokens(truncated)

        # Verify truncation worked
        assert truncated_count <= original_count // 2
        assert truncated_count > 0

    def test_message_overhead_consistency(self):
        """Verify message overhead is consistent across message types."""
        content = "Same content for all"
        messages = [
            HumanMessage(content=content),
            AIMessage(content=content),
            SystemMessage(content=content),
        ]

        # All should have same token count (same content + same overhead)
        counts = [count_message_tokens(m) for m in messages]
        assert len(set(counts)) == 1  # All the same
