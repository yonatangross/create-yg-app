"""Memory extraction service using LLM to identify key information.

Analyzes conversations and extracts:
- User preferences (likes, dislikes, settings)
- Learned facts (personal info, work, location)
- Key insights (realizations, patterns)
"""

# ruff: noqa: E501
import json
from dataclasses import dataclass

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.core.logging import get_logger
from app.db.models.memory import MemoryType
from app.llm.factory import LLMFactory

logger = get_logger(__name__)

# Extraction prompt - instructs LLM to identify memorable information
# Note: Double braces {{}} escape the braces so .format() doesn't interpret them
EXTRACTION_PROMPT = """Analyze this conversation and extract any information worth remembering about the user.

Return a JSON array of extracted memories. Each memory should have:
- "type": one of "user_preference", "learned_fact", or "key_insight"
- "content": the information to remember (concise, standalone sentence)

Guidelines:
- user_preference: Things the user likes, dislikes, prefers, or wants
- learned_fact: Personal information like name, job, location, skills
- key_insight: Important realizations or patterns about the user

Only extract NEW information from this conversation. Be selective - only include truly valuable facts that would help personalize future responses.

If there's nothing worth extracting, return an empty array: []

Examples of good extractions:
- {{"type": "learned_fact", "content": "User works as a software engineer at Google"}}
- {{"type": "user_preference", "content": "User prefers TypeScript over JavaScript"}}
- {{"type": "key_insight", "content": "User is building an AI startup and values practical advice"}}

Conversation to analyze:
{conversation}

Return ONLY valid JSON array, no other text:"""


@dataclass
class ExtractedMemory:
    """A memory extracted from conversation."""

    memory_type: MemoryType
    content: str


class MemoryExtractionService:
    """Extract memorable information from conversations using LLM.

    Uses a lightweight model (gpt-4o-mini) for cost-effective extraction.

    Example:
        service = MemoryExtractionService()
        memories = await service.extract_from_messages(messages)
        for m in memories:
            await memory_service.store(m.content, m.memory_type)
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        """Initialize extraction service.

        Args:
            model: LLM model to use for extraction (default: gpt-4o-mini for speed/cost)
        """
        self.model = model
        self._llm = None

    def _get_llm(self):
        """Lazy-load LLM to avoid initialization overhead."""
        if self._llm is None:
            self._llm = LLMFactory.create(
                model=self.model,
                temperature=0.0,  # Deterministic for consistent extraction
                timeout=30.0,
            )
        return self._llm

    def _format_conversation(self, messages: list[BaseMessage]) -> str:
        """Format messages for the extraction prompt.

        Args:
            messages: List of conversation messages

        Returns:
            Formatted string representation of conversation
        """
        lines = []
        for msg in messages:
            role = "User" if isinstance(msg, HumanMessage) else "Assistant"
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _parse_type(self, type_str: str) -> MemoryType | None:
        """Convert string type to MemoryType enum.

        Args:
            type_str: Type string from LLM response

        Returns:
            MemoryType enum value or None if invalid
        """
        type_map = {
            "user_preference": MemoryType.USER_PREFERENCE,
            "learned_fact": MemoryType.LEARNED_FACT,
            "key_insight": MemoryType.KEY_INSIGHT,
        }
        return type_map.get(type_str.lower())

    async def extract_from_messages(
        self,
        messages: list[BaseMessage],
        min_messages: int = 2,
    ) -> list[ExtractedMemory]:
        """Extract memories from conversation messages.

        Args:
            messages: List of conversation messages to analyze
            min_messages: Minimum messages required for extraction (default: 2)

        Returns:
            List of extracted memories (may be empty)
        """
        # Skip if conversation too short
        if len(messages) < min_messages:
            logger.debug(
                "extraction_skipped_short_conversation",
                message_count=len(messages),
                min_required=min_messages,
            )
            return []

        # Format conversation for prompt
        conversation_text = self._format_conversation(messages)

        # Build extraction prompt
        prompt = EXTRACTION_PROMPT.format(conversation=conversation_text)

        try:
            llm = self._get_llm()
            response = await llm.ainvoke([SystemMessage(content=prompt)])

            # Parse JSON response
            response_text = (
                response.content if isinstance(response.content, str) else str(response.content)
            )

            # Clean up response (remove markdown code blocks if present)
            response_text = response_text.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("\n", 1)[1]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()

            extracted_data = json.loads(response_text)

            logger.debug(
                "extraction_raw_response",
                response_text=response_text[:500],
                parsed_data=str(extracted_data)[:200],
            )

            # Handle case where LLM returns a single object instead of array
            if isinstance(extracted_data, dict):
                extracted_data = [extracted_data]
            elif not isinstance(extracted_data, list):
                logger.warning(
                    "extraction_unexpected_format", data_type=type(extracted_data).__name__
                )
                return []

            # Convert to ExtractedMemory objects
            memories = []
            for item in extracted_data:
                # Skip non-dict items
                if not isinstance(item, dict):
                    logger.debug("extraction_skipping_non_dict_item", item=str(item)[:100])
                    continue

                memory_type = self._parse_type(item.get("type", ""))
                content = item.get("content", "").strip()

                if memory_type and content:
                    memories.append(ExtractedMemory(memory_type=memory_type, content=content))

            logger.info(
                "extraction_complete",
                message_count=len(messages),
                memories_extracted=len(memories),
            )

            return memories

        except json.JSONDecodeError as e:
            logger.warning(
                "extraction_json_parse_error",
                error=str(e),
                response_preview=response_text[:200] if response_text else None,
            )
            return []
        except Exception as e:
            logger.warning(
                "extraction_failed",
                error=str(e),
                error_type=type(e).__name__,
                response_preview=response_text[:200] if "response_text" in dir() else None,
            )
            return []

    async def extract_and_store(
        self,
        messages: list[BaseMessage],
        memory_service,
        conversation_id: str | None = None,
    ) -> int:
        """Extract memories and store them directly.

        Convenience method that combines extraction and storage.

        Args:
            messages: Conversation messages to analyze
            memory_service: MemoryService instance for storage
            conversation_id: Optional conversation ID for linking

        Returns:
            Number of memories stored
        """
        memories = await self.extract_from_messages(messages)

        stored_count = 0
        for mem in memories:
            try:
                await memory_service.store(
                    content=mem.content,
                    memory_type=mem.memory_type,
                    conversation_id=conversation_id,
                )
                stored_count += 1
            except Exception as e:
                logger.warning(
                    "memory_store_failed",
                    content_preview=mem.content[:50],
                    error=str(e),
                )

        logger.info(
            "extraction_and_store_complete",
            extracted=len(memories),
            stored=stored_count,
            conversation_id=conversation_id,
        )

        return stored_count


# Singleton instance for reuse
_extraction_service: MemoryExtractionService | None = None


def get_extraction_service() -> MemoryExtractionService:
    """Get singleton extraction service instance."""
    global _extraction_service
    if _extraction_service is None:
        _extraction_service = MemoryExtractionService()
    return _extraction_service
