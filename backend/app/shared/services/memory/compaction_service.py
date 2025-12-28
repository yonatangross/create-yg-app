"""Conversation compaction service for long-running sessions.

Compresses old messages into summaries to save context window tokens
while preserving important information.

Architecture:
    - Keeps recent N messages verbatim (full context)
    - Summarizes older messages into a compressed format
    - Stores summaries in PostgreSQL for cross-session persistence

Example:
    compactor = SessionCompactor(session, embedding_service)
    result = await compactor.compact(messages, conversation_id)
    # result.summary = "User discussed React hooks..."
    # result.recent_messages = [last 5 messages]
"""

# ruff: noqa: E501
from dataclasses import dataclass

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.core.logging import get_logger
from app.llm.factory import LLMFactory
from app.shared.services.memory.memory_service import MemoryService

logger = get_logger(__name__)


@dataclass
class CompactionConfig:
    """Configuration for conversation compaction.

    Attributes:
        max_turns_verbatim: Number of recent message pairs to keep verbatim.
        compaction_threshold: Trigger compaction when messages exceed this count.
        summary_max_tokens: Maximum tokens for the summary.
        preserve_system_messages: Whether to keep system messages in verbatim section.
    """

    max_turns_verbatim: int = 5  # Keep last 5 exchanges (10 messages)
    compaction_threshold: int = 15  # Compact when > 15 messages
    summary_max_tokens: int = 500
    preserve_system_messages: bool = True


@dataclass
class CompactionResult:
    """Result of conversation compaction.

    Attributes:
        summary: Compressed summary of older messages (None if no compaction needed).
        recent_messages: Recent messages kept verbatim.
        was_compacted: Whether compaction was performed.
        original_count: Number of messages before compaction.
        compacted_count: Number of messages that were summarized.
    """

    summary: str | None
    recent_messages: list[BaseMessage]
    was_compacted: bool
    original_count: int
    compacted_count: int


# Summarization prompt - focuses on key information for context
SUMMARIZATION_PROMPT = """Summarize this conversation concisely for use as context in future messages.

Focus on:
- Key topics discussed and conclusions reached
- User preferences or requirements mentioned
- Important decisions or agreements made
- Any unresolved questions or pending items

Keep the summary factual and neutral. Use 2-4 sentences maximum.

Conversation to summarize:
{conversation}

Summary:"""


class SessionCompactor:
    """Compresses long conversations into summaries.

    Uses an LLM to summarize older messages while keeping recent ones verbatim.
    This preserves context while reducing token usage.

    Example:
        async with get_session() as session:
            compactor = SessionCompactor(session, embedding_service)

            # Compact if needed
            result = await compactor.compact(messages, "conv-123")

            if result.was_compacted:
                print(f"Compacted {result.compacted_count} messages")
                print(f"Summary: {result.summary}")

            # Use result.recent_messages for LLM context
    """

    def __init__(
        self,
        memory_service: MemoryService,
        config: CompactionConfig | None = None,
        model: str = "gpt-4o-mini",
    ) -> None:
        """Initialize the compactor.

        Args:
            memory_service: Service for storing summaries as memories.
            config: Compaction configuration (uses defaults if None).
            model: LLM model for summarization (default: gpt-4o-mini for speed/cost).
        """
        self.memory_service = memory_service
        self.config = config or CompactionConfig()
        self.model = model
        self._llm = None

    def _get_llm(self):
        """Lazy-load LLM to avoid initialization overhead."""
        if self._llm is None:
            self._llm = LLMFactory.create(
                model=self.model,
                temperature=0.3,  # Slightly creative for natural summaries
                timeout=30.0,
            )
        return self._llm

    def _format_messages_for_summary(self, messages: list[BaseMessage]) -> str:
        """Format messages into a string for summarization.

        Args:
            messages: List of messages to format.

        Returns:
            Formatted string representation.
        """
        lines = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                role = "User"
            elif isinstance(msg, AIMessage):
                role = "Assistant"
            elif isinstance(msg, SystemMessage):
                continue  # Skip system messages in summary
            else:
                role = "Unknown"

            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            # Truncate very long messages
            if len(content) > 500:
                content = content[:500] + "..."
            lines.append(f"{role}: {content}")

        return "\n".join(lines)

    def _split_messages(
        self, messages: list[BaseMessage]
    ) -> tuple[list[BaseMessage], list[BaseMessage]]:
        """Split messages into old (to summarize) and recent (to keep).

        Args:
            messages: Full list of conversation messages.

        Returns:
            Tuple of (messages_to_summarize, recent_messages).
        """
        # Calculate how many messages to keep verbatim
        # max_turns_verbatim * 2 because each turn = user + assistant
        keep_count = self.config.max_turns_verbatim * 2

        if len(messages) <= keep_count:
            return [], messages

        # Split: older messages for summary, recent ones kept verbatim
        split_point = len(messages) - keep_count
        return messages[:split_point], messages[split_point:]

    async def _generate_summary(self, messages: list[BaseMessage]) -> str:
        """Generate a summary of the given messages using LLM.

        Args:
            messages: Messages to summarize.

        Returns:
            Summary string.
        """
        conversation_text = self._format_messages_for_summary(messages)
        prompt = SUMMARIZATION_PROMPT.format(conversation=conversation_text)

        llm = self._get_llm()
        response = await llm.ainvoke([SystemMessage(content=prompt)])

        summary = response.content if isinstance(response.content, str) else str(response.content)

        logger.debug(
            "summary_generated",
            input_messages=len(messages),
            summary_length=len(summary),
        )

        return summary.strip()

    async def compact(
        self,
        messages: list[BaseMessage],
        conversation_id: str,
    ) -> CompactionResult:
        """Compact conversation if it exceeds threshold.

        If the conversation is long enough, older messages are summarized
        and the summary is stored for future reference.

        Args:
            messages: Full conversation history.
            conversation_id: Unique identifier for the conversation.

        Returns:
            CompactionResult with summary and recent messages.
        """
        original_count = len(messages)

        # Check if compaction is needed
        if original_count <= self.config.compaction_threshold:
            logger.debug(
                "compaction_skipped",
                conversation_id=conversation_id,
                message_count=original_count,
                threshold=self.config.compaction_threshold,
            )
            return CompactionResult(
                summary=None,
                recent_messages=messages,
                was_compacted=False,
                original_count=original_count,
                compacted_count=0,
            )

        # Split messages
        to_summarize, recent = self._split_messages(messages)

        if not to_summarize:
            return CompactionResult(
                summary=None,
                recent_messages=recent,
                was_compacted=False,
                original_count=original_count,
                compacted_count=0,
            )

        # Check for existing summary to append to
        existing_summary = await self.memory_service.get_conversation_summary(conversation_id)

        try:
            # Generate new summary
            new_summary = await self._generate_summary(to_summarize)

            # Combine with existing summary if present
            if existing_summary and existing_summary.summary:
                combined_summary = f"{existing_summary.summary}\n\nMore recently: {new_summary}"
                # Truncate if too long
                if len(combined_summary) > 1500:
                    combined_summary = combined_summary[-1500:]
            else:
                combined_summary = new_summary

            # Save the summary
            await self.memory_service.save_conversation_summary(
                conversation_id=conversation_id,
                summary=combined_summary,
                message_count=original_count,
            )

            logger.info(
                "compaction_complete",
                conversation_id=conversation_id,
                original_count=original_count,
                compacted_count=len(to_summarize),
                kept_verbatim=len(recent),
                summary_length=len(combined_summary),
            )

            return CompactionResult(
                summary=combined_summary,
                recent_messages=recent,
                was_compacted=True,
                original_count=original_count,
                compacted_count=len(to_summarize),
            )

        except Exception as e:
            logger.warning(
                "compaction_failed",
                conversation_id=conversation_id,
                error=str(e),
            )
            # Return original messages on failure
            return CompactionResult(
                summary=None,
                recent_messages=messages,
                was_compacted=False,
                original_count=original_count,
                compacted_count=0,
            )

    async def get_context_with_summary(
        self,
        messages: list[BaseMessage],
        conversation_id: str,
    ) -> tuple[str | None, list[BaseMessage]]:
        """Get conversation context, loading existing summary if available.

        This is useful at the start of a session to restore context.

        Args:
            messages: Current session messages.
            conversation_id: Conversation identifier.

        Returns:
            Tuple of (existing_summary, messages).
        """
        # Try to load existing summary
        existing = await self.memory_service.get_conversation_summary(conversation_id)

        if existing and existing.summary:
            logger.debug(
                "loaded_existing_summary",
                conversation_id=conversation_id,
                summary_length=len(existing.summary),
                message_count=existing.message_count,
            )
            return existing.summary, messages

        return None, messages


# Convenience function
async def compact_if_needed(
    messages: list[BaseMessage],
    conversation_id: str,
    memory_service: MemoryService,
    config: CompactionConfig | None = None,
) -> CompactionResult:
    """Convenience function to compact conversation if needed.

    Args:
        messages: Conversation messages.
        conversation_id: Conversation identifier.
        memory_service: Memory service instance.
        config: Optional compaction configuration.

    Returns:
        CompactionResult with summary and recent messages.
    """
    compactor = SessionCompactor(memory_service, config)
    return await compactor.compact(messages, conversation_id)
