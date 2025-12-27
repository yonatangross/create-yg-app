"""Agent-to-memory-type mapping for context optimization.

Different agent types need different memory types for context efficiency.
This module provides mappings and utilities for filtering memories by agent.
"""

from app.db.models.memory import MemoryType

# Agent-specific memory type mappings
# None value means agent uses all memory types
AGENT_MEMORY_MAP: dict[str, list[MemoryType]] = {
    "chat": [
        MemoryType.USER_PREFERENCE,
        MemoryType.LEARNED_FACT,
    ],
    "code_review": [
        MemoryType.KEY_INSIGHT,
        MemoryType.LEARNED_FACT,
    ],
    "analysis": [
        MemoryType.CONVERSATION_SUMMARY,
        MemoryType.KEY_INSIGHT,
    ],
    "tutor": [
        MemoryType.USER_PREFERENCE,
        MemoryType.LEARNED_FACT,
    ],
}


def get_memory_types_for_agent(agent_type: str) -> list[MemoryType] | None:
    """Get relevant memory types for a specific agent.

    Args:
        agent_type: The agent identifier (e.g., "chat", "code_review").

    Returns:
        List of MemoryType enums if agent has specific mapping,
        None if agent should use all memory types.

    Examples:
        >>> get_memory_types_for_agent("chat")
        [MemoryType.USER_PREFERENCE, MemoryType.LEARNED_FACT]

        >>> get_memory_types_for_agent("unknown_agent")
        None  # Uses all memory types
    """
    return AGENT_MEMORY_MAP.get(agent_type)


def should_include_memory_type(agent_type: str, memory_type: MemoryType) -> bool:
    """Check if a memory type is relevant for an agent.

    Args:
        agent_type: The agent identifier.
        memory_type: The memory type to check.

    Returns:
        True if the memory type should be included for this agent,
        False otherwise.

    Examples:
        >>> should_include_memory_type("chat", MemoryType.USER_PREFERENCE)
        True

        >>> should_include_memory_type("chat", MemoryType.KEY_INSIGHT)
        False

        >>> should_include_memory_type("unknown", MemoryType.LEARNED_FACT)
        True  # Unknown agents get all types
    """
    allowed_types = get_memory_types_for_agent(agent_type)

    # None means all types allowed
    if allowed_types is None:
        return True

    return memory_type in allowed_types
