"""Token counting utilities using tiktoken.

This module provides accurate token counting for LLM context management.
Uses tiktoken's cl100k_base encoding (GPT-4, GPT-3.5-turbo compatible).

Reference: .claude/skills/context-engineering/SKILL.md
"""

from functools import lru_cache

import tiktoken
from langchain_core.messages import BaseMessage


@lru_cache(maxsize=1)
def get_encoding() -> tiktoken.Encoding:
    """Get cached tiktoken encoding.

    Uses cl100k_base encoding which is compatible with:
    - GPT-4 (all variants)
    - GPT-3.5-turbo
    - text-embedding-ada-002

    Returns:
        Cached tiktoken encoding instance
    """
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken.

    Args:
        text: Input text to count tokens for

    Returns:
        Number of tokens in the text
    """
    return len(get_encoding().encode(text))


def count_message_tokens(message: BaseMessage) -> int:
    """Count tokens in a LangChain message.

    Includes overhead for message structure:
    - Role identifier: ~1 token
    - Message delimiters: ~3 tokens

    Args:
        message: LangChain BaseMessage instance

    Returns:
        Total tokens including message overhead
    """
    content = message.content if isinstance(message.content, str) else str(message.content)
    tokens = count_tokens(content)
    # Add overhead for message structure (~4 tokens per message)
    return tokens + 4


def count_messages_tokens(messages: list[BaseMessage]) -> int:
    """Count total tokens in message list.

    Args:
        messages: List of LangChain messages

    Returns:
        Sum of tokens across all messages
    """
    return sum(count_message_tokens(m) for m in messages)


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to fit within token limit.

    Truncates at exact token boundary (not character boundary).

    Args:
        text: Input text to truncate
        max_tokens: Maximum number of tokens to keep

    Returns:
        Truncated text that fits within max_tokens
    """
    encoding = get_encoding()
    tokens = encoding.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return encoding.decode(tokens[:max_tokens])


def get_token_budget_messages(
    messages: list[BaseMessage],
    token_budget: int,
) -> list[BaseMessage]:
    """Get messages that fit within token budget (most recent first).

    Preserves message order while fitting within budget.
    Always keeps at least one message if possible.

    Args:
        messages: List of messages to filter
        token_budget: Maximum tokens allowed

    Returns:
        Filtered list of messages that fit within budget
    """
    result = []
    total = 0
    for msg in reversed(messages):
        msg_tokens = count_message_tokens(msg)
        if total + msg_tokens > token_budget:
            break
        result.insert(0, msg)
        total += msg_tokens
    return result
