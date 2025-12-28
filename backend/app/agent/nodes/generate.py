"""Generate node for LLM response generation."""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent.state import AgentState
from app.core.logging import get_logger
from app.llm.factory import get_llm

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a helpful AI assistant. Provide clear, accurate, and helpful responses.

If context is provided, use it to inform your response. If you don't know something, say so.

Be concise but thorough. Use markdown formatting when appropriate."""


async def generate_node(state: AgentState) -> dict:
    """Generate a response using the LLM.

    Args:
        state: Current agent state with query and optional context.

    Returns:
        Updated state with generated response.
    """
    query = state.get("query", "")
    retrieved_chunks = state.get("retrieved_chunks", [])
    messages = state.get("messages", [])
    proactive_context = state.get("proactive_context", "")
    conversation_summary = state.get("conversation_summary", "")

    logger.info("generating_response", query=query[:100])

    # Build system prompt with proactive context and conversation summary
    # Order: proactive_context -> conversation_summary -> base prompt
    system_parts = []

    if proactive_context:
        system_parts.append(proactive_context)
        logger.info("using_proactive_context", context_length=len(proactive_context))

    if conversation_summary:
        system_parts.append(f"## Earlier Conversation Summary\n{conversation_summary}")
        logger.info("using_conversation_summary", summary_length=len(conversation_summary))

    system_parts.append(SYSTEM_PROMPT)
    system_content = "\n---\n".join(system_parts)

    # Build context from retrieved chunks
    context = ""
    if retrieved_chunks:
        context = "\n\n".join(chunk.get("content", "") for chunk in retrieved_chunks)
        context = f"\n\nContext:\n{context}"

    # Build message list
    llm_messages = [
        SystemMessage(content=system_content + context),
        *messages,
        HumanMessage(content=query),
    ]

    # Get LLM and generate response
    llm = get_llm()
    response = await llm.ainvoke(llm_messages)

    return {
        "response": response.content,
        "messages": [
            HumanMessage(content=query),
            AIMessage(content=response.content),
        ],
    }
