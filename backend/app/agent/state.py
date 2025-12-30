"""Agent state definition using TypedDict with annotated reducers."""

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage


class AgentState(TypedDict, total=False):
    """State for the agent workflow.

    Uses Annotated types with reducers for parallel-safe state updates.
    The operator.add reducer allows multiple nodes to append to lists
    without conflicts during parallel execution.
    """

    # Input
    query: str
    conversation_id: str

    # Messages - uses add reducer for parallel safety
    messages: Annotated[list[BaseMessage], operator.add]

    # Retrieved context for RAG
    retrieved_chunks: Annotated[list[dict], operator.add]

    # Control flow
    current_step: str
    should_retrieve: bool

    # Long-term memory context injected into system prompt
    # This field holds persistent context from previous conversations
    # that should influence the agent's behavior and responses
    proactive_context: str

    # Conversation summary from compaction
    # This is a compressed version of older messages in the conversation,
    # used to maintain context continuity while saving tokens
    conversation_summary: str

    # Output
    response: str
