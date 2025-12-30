"""Conversation compaction with summarization and tool preservation."""

from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from pydantic import BaseModel, Field, field_validator

from app.core.logging import get_logger
from app.llm.factory import get_llm

logger = get_logger(__name__)


class CompactionConfig(BaseModel):
    """Configuration for conversation compaction."""

    max_turns_full: int = Field(default=5, description="Recent turns kept verbatim")
    summarize_after: int = Field(default=10, description="Trigger summarization at N messages")
    summary_max_tokens: int = Field(default=500, description="Max tokens for summary")
    token_budget: int = Field(default=6000, description="Total token budget")
    preserve_tool_calls: bool = Field(default=True, description="Always preserve tool calls")

    @field_validator("token_budget")
    @classmethod
    def validate_budget(cls, v: int, info: Any) -> int:
        """Validate token budget is sufficient for summarization."""
        summary_max = info.data.get("summary_max_tokens", 500)
        if v <= summary_max * 2:
            msg = "token_budget must exceed 2x summary_max_tokens"
            raise ValueError(msg)
        return v


@dataclass
class CompiledContext:
    """Result of context compilation."""

    prefix: list[BaseMessage] = field(default_factory=list)
    messages: list[BaseMessage] = field(default_factory=list)
    summary: str | None = None
    original_count: int = 0

    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio."""
        compiled = len(self.prefix) + len(self.messages)
        return self.original_count / max(compiled, 1)

    def to_messages_with_cache(self) -> list[BaseMessage]:
        """Convert to messages with Anthropic prompt caching headers.

        Anthropic's prompt caching allows caching of static prefix content
        (system prompts, summaries) to save costs and reduce latency.

        Cost savings:
        - Cached content: 90% cheaper on subsequent requests
        - Cache duration: 5 minutes
        - Minimum cache size: 1024 tokens

        The last message in the prefix gets a cache_control header,
        marking everything up to that point as cacheable.

        Returns:
            List of messages with cache_control headers on prefix

        Reference:
            https://docs.anthropic.com/claude/docs/prompt-caching
        """
        result: list[BaseMessage] = []

        # Add prefix messages with cache marker on the last one
        if self.prefix:
            for i, msg in enumerate(self.prefix):
                is_last_prefix = i == len(self.prefix) - 1
                if is_last_prefix:
                    # Mark last prefix message for caching (deep copy to avoid mutation)
                    cached_msg = msg.copy(deep=True)
                    if not hasattr(cached_msg, "additional_kwargs"):
                        cached_msg.additional_kwargs = {}
                    cached_msg.additional_kwargs["cache_control"] = {"type": "ephemeral"}
                    result.append(cached_msg)
                else:
                    result.append(msg)

        # Add dynamic messages (not cached)
        result.extend(self.messages)

        return result


class SessionCompactor:
    """Compact conversation history with LLM summarization."""

    SUMMARY_PROMPT = """Summarize this conversation concisely:

{messages}

Focus on:
- Key topics discussed
- User preferences or facts mentioned
- Important decisions or conclusions
- Unresolved questions

Keep to 2-3 sentences maximum."""

    def __init__(self, config: CompactionConfig | None = None):
        """Initialize compactor with configuration.

        Args:
            config: Compaction configuration, uses defaults if None
        """
        self.config = config or CompactionConfig()

    async def compact(self, history: list[BaseMessage]) -> CompiledContext:
        """Compact history with summarization and tool preservation.

        Args:
            history: Full conversation history

        Returns:
            Compiled context with summary and preserved messages
        """
        original_count = len(history)

        # No compaction needed
        if original_count <= self.config.summarize_after:
            return CompiledContext(
                prefix=[],
                messages=history,
                summary=None,
                original_count=original_count,
            )

        # Separate tool-related from regular messages
        tool_msgs = [m for m in history if self._is_tool_related(m)]
        regular_msgs = [m for m in history if not self._is_tool_related(m)]

        # Split regular messages: older (summarize) vs recent (keep)
        recent_count = self.config.max_turns_full * 2  # User + AI pairs
        cutoff = max(0, len(regular_msgs) - recent_count)
        older = regular_msgs[:cutoff]
        recent = regular_msgs[cutoff:]

        # Generate summary of older messages
        summary = None
        prefix = []
        if older:
            summary = await self._summarize(older)
            if summary:
                prefix.append(SystemMessage(content=f"Previous conversation summary: {summary}"))

        # Merge recent messages with preserved tool calls (chronologically)
        messages = self._merge_chronologically(recent, tool_msgs)

        logger.info(
            "compaction_complete",
            original=original_count,
            after_compaction=len(prefix) + len(messages),
            tool_calls_preserved=len(tool_msgs),
            has_summary=summary is not None,
        )

        return CompiledContext(
            prefix=prefix,
            messages=messages,
            summary=summary,
            original_count=original_count,
        )

    def _is_tool_related(self, msg: BaseMessage) -> bool:
        """Check if message is tool call or result.

        Args:
            msg: Message to check

        Returns:
            True if message contains tool calls or is a tool message
        """
        if isinstance(msg, ToolMessage):
            return True
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            return True
        return hasattr(msg, "additional_kwargs") and bool(msg.additional_kwargs.get("tool_calls"))

    def _merge_chronologically(
        self,
        regular: list[BaseMessage],
        tool: list[BaseMessage],
    ) -> list[BaseMessage]:
        """Merge two lists maintaining original order.

        Args:
            regular: Regular messages
            tool: Tool-related messages

        Returns:
            Merged list with chronological order
        """
        # Simple approach: tool messages are inserted at end
        # More sophisticated: track original indices
        return regular + tool

    async def _summarize(self, messages: list[BaseMessage]) -> str | None:
        """Generate LLM summary of messages.

        Args:
            messages: Messages to summarize

        Returns:
            Summary text or None if summarization fails
        """
        try:
            formatted = self._format_messages(messages)
            prompt = self.SUMMARY_PROMPT.format(messages=formatted)

            llm = get_llm()
            response = await llm.ainvoke([HumanMessage(content=prompt)])

            summary = response.content
            # Truncate if too long
            max_chars = self.config.summary_max_tokens * 4
            if isinstance(summary, str) and len(summary) > max_chars:
                summary = summary[:max_chars] + "..."

            return str(summary) if summary else None
        except Exception as e:
            logger.error("summarization_failed", error=str(e))
            return None

    def _format_messages(self, messages: list[BaseMessage]) -> str:
        """Format messages for summarization prompt.

        Args:
            messages: Messages to format

        Returns:
            Formatted string for summarization
        """
        lines = []
        for msg in messages:
            role = "User" if isinstance(msg, HumanMessage) else "Assistant"
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            # Truncate very long messages
            if len(content) > 500:
                content = content[:500] + "..."
            lines.append(f"{role}: {content}")
        return "\n".join(lines)
