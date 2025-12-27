"""LangChain tools for agent self-serve memory recall.

Provides reactive memory search as a tool that LLM agents can invoke to recall
relevant information from long-term storage.
"""

from langchain_core.tools import tool

from app.core.logging import get_logger
from app.db.models.memory import MemoryType
from app.db.session import get_session
from app.shared.services.memory.embedding_service import get_embedding_service
from app.shared.services.memory.memory_service import MemoryService

logger = get_logger(__name__)


@tool
async def search_memory(
    query: str,
    memory_type: str | None = None,
) -> str:
    """Search long-term memory for relevant information.

    Use this tool when you:
    - Need to recall specific facts from past conversations
    - Want to check user preferences or settings
    - Need context about previous decisions or analysis
    - Are unsure about something discussed earlier

    Args:
        query: What to search for (be specific for better results)
        memory_type: Optional filter - one of: user_preference, learned_fact,
                     conversation_summary, key_insight

    Returns:
        Relevant memories with similarity scores, or message if none found.

    Examples:
        - search_memory("user's favorite color")
        - search_memory("previous analysis", memory_type="key_insight")
    """
    logger.debug(
        "search_memory_tool_invoked",
        query=query,
        memory_type=memory_type,
    )

    try:
        # Validate memory_type if provided
        memory_type_enum = None
        if memory_type:
            try:
                memory_type_enum = MemoryType(memory_type)
            except ValueError:
                valid_types = ", ".join([t.value for t in MemoryType])
                return f"Invalid memory_type '{memory_type}'. Valid types: {valid_types}"

        # Execute search with async context manager
        async with get_session() as session:
            embedding_service = get_embedding_service()
            service = MemoryService(session, embedding_service)

            results = await service.search(
                query=query,
                memory_type=memory_type_enum,
                limit=3,
                threshold=0.6,
            )

        if not results:
            logger.debug("search_memory_no_results", query=query)
            return "No relevant memories found for this query."

        # Format results for agent consumption
        lines = ["Found relevant memories:"]
        for i, r in enumerate(results, 1):
            type_label = r.memory.memory_type.replace("_", " ").title()
            lines.append(f"\n{i}. [{type_label}] (similarity: {r.similarity:.0%})")
            lines.append(f"   {r.memory.content}")

        result_str = "\n".join(lines)

        logger.info(
            "search_memory_success",
            query=query,
            results_count=len(results),
            top_similarity=results[0].similarity,
        )

        return result_str

    except Exception as e:
        logger.error(
            "search_memory_error",
            query=query,
            error=str(e),
            exc_info=True,
        )
        return f"Error searching memory: {e}"


__all__ = ["search_memory"]
