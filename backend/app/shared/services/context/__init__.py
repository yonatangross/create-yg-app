"""Context management services.

Provides token counting, context compilation, and context window management utilities.
"""

from .compaction import CompactionConfig, CompiledContext, SessionCompactor
from .compiler import CompilerResult, ContextCompiler
from .token_counter import (
    count_message_tokens,
    count_messages_tokens,
    count_tokens,
    get_token_budget_messages,
    truncate_to_tokens,
)

__all__ = [
    # Compaction
    "CompactionConfig",
    "CompiledContext",
    "SessionCompactor",
    # Compilation
    "CompilerResult",
    "ContextCompiler",
    # Token counting
    "count_tokens",
    "count_message_tokens",
    "count_messages_tokens",
    "truncate_to_tokens",
    "get_token_budget_messages",
]
