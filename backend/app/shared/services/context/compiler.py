"""Context compiler for LLM invocations.

This module implements the ContextCompiler class that orchestrates the assembly
of context for LLM calls. It integrates conversation compaction, proactive memory,
and proper message ordering.

Reference: .claude/skills/context-engineering/SKILL.md (Issue #7)
"""

from dataclasses import dataclass

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.core.logging import get_logger
from app.shared.services.context.compaction import CompiledContext, SessionCompactor
from app.shared.services.context.token_counter import count_messages_tokens

logger = get_logger(__name__)


@dataclass
class CompilerResult:
    """Result of context compilation with metrics.

    Attributes:
        messages: Ordered messages ready for LLM invocation
        metrics: Compilation metrics for observability
    """

    messages: list[BaseMessage]
    metrics: dict[str, int | float]

    @property
    def total_tokens(self) -> int:
        """Calculate total tokens in compiled context."""
        return int(self.metrics.get("total_tokens", 0))

    @property
    def compression_ratio(self) -> float:
        """Get compression ratio from metrics."""
        return self.metrics.get("compression_ratio", 1.0)


class ContextCompiler:
    """Compile context for LLM invocations with proper ordering.

    This class orchestrates the assembly of context for LLM calls:
    1. System prompt (first)
    2. Proactive memory context
    3. Compacted prefix (summaries)
    4. Recent messages
    5. Current input (last)

    Example:
        >>> compiler = ContextCompiler(compactor)
        >>> result = await compiler.compile(
        ...     system_prompt="You are a helpful assistant.",
        ...     history=[HumanMessage(content="Hello")],
        ...     proactive_context="User prefers dark mode.",
        ...     current_input="What's my preference?",
        ... )
        >>> messages = result.messages
        >>> print(f"Total tokens: {result.total_tokens}")
    """

    def __init__(self, compactor: SessionCompactor | None = None):
        """Initialize ContextCompiler.

        Args:
            compactor: SessionCompactor instance for history compaction.
                      If None, creates a default compactor.
        """
        self.compactor = compactor or SessionCompactor()

    async def compile(
        self,
        system_prompt: str,
        history: list[BaseMessage],
        current_input: str,
        proactive_context: str | None = None,
    ) -> CompilerResult:
        """Compile context for LLM invocation.

        Assembles context in proper order:
        1. System prompt (first - sets LLM behavior)
        2. Proactive memory context (if provided)
        3. Compacted history (summaries + recent messages)
        4. Current input (last - what user is asking now)

        Args:
            system_prompt: System prompt to set LLM behavior
            history: Full conversation history to be compacted
            current_input: Current user input
            proactive_context: Optional proactive memory context

        Returns:
            CompilerResult with ordered messages and metrics

        Raises:
            ValueError: If system_prompt or current_input is empty
        """
        # Validate inputs
        if not system_prompt or not system_prompt.strip():
            msg = "system_prompt cannot be empty"
            raise ValueError(msg)
        if not current_input or not current_input.strip():
            msg = "current_input cannot be empty"
            raise ValueError(msg)

        result: list[BaseMessage] = []
        original_history_count = len(history)

        # 1. System prompt (always first)
        result.append(SystemMessage(content=system_prompt))

        # 2. Proactive memory context (before history)
        if proactive_context and proactive_context.strip():
            result.append(
                SystemMessage(content=f"## Relevant Context from Memory\n\n{proactive_context}")
            )

        # 3. Compacted history (prefix + recent messages)
        compacted: CompiledContext = await self.compactor.compact(history)

        # Add prefix (summaries as system messages)
        result.extend(compacted.prefix)

        # Add recent messages
        result.extend(compacted.messages)

        # 4. Current input (always last)
        result.append(HumanMessage(content=current_input))

        # Calculate metrics
        total_tokens = count_messages_tokens(result)
        compression_ratio = compacted.compression_ratio

        metrics = {
            "original_history_count": original_history_count,
            "compacted_history_count": len(compacted.messages),
            "prefix_count": len(compacted.prefix),
            "has_summary": compacted.summary is not None,
            "has_proactive_context": bool(proactive_context and proactive_context.strip()),
            "total_messages": len(result),
            "total_tokens": total_tokens,
            "compression_ratio": compression_ratio,
        }

        logger.info(
            "context_compilation_complete",
            **metrics,
        )

        return CompilerResult(messages=result, metrics=metrics)

    async def compile_simple(
        self,
        system_prompt: str,
        current_input: str,
    ) -> CompilerResult:
        """Compile simple context without history or proactive memory.

        Convenience method for single-turn interactions.

        Args:
            system_prompt: System prompt to set LLM behavior
            current_input: Current user input

        Returns:
            CompilerResult with ordered messages and metrics
        """
        return await self.compile(
            system_prompt=system_prompt,
            history=[],
            current_input=current_input,
            proactive_context=None,
        )
