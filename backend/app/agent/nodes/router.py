"""Router node for deciding workflow paths."""

from app.agent.state import AgentState


def should_retrieve(state: AgentState) -> str:
    """Decide if retrieval is needed based on state.

    Args:
        state: Current agent state.

    Returns:
        Next node to execute: "retrieve" or "end"
    """
    # If we already have a response, we're done
    if state.get("response"):
        return "end"

    # If retrieval is explicitly requested
    if state.get("should_retrieve"):
        return "retrieve"

    # Default: skip retrieval for now (can be enhanced with intent detection)
    return "end"
