"""LangGraph workflow definition."""

from functools import lru_cache

from langgraph.graph import END, StateGraph

from app.agent.nodes.generate import generate_node
from app.agent.nodes.retrieve import retrieve_node
from app.agent.nodes.router import should_retrieve
from app.agent.state import AgentState
from app.core.logging import get_logger

logger = get_logger(__name__)


def create_agent_graph() -> StateGraph:
    """Create the agent workflow graph.

    The graph implements a simple RAG pattern:
    1. Router decides if retrieval is needed
    2. If yes, retrieve relevant chunks
    3. Generate response using LLM

    Returns:
        Compiled LangGraph workflow.
    """
    # Create the graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)

    # Set entry point - always start with router decision
    graph.set_entry_point("generate")

    # Add conditional edges for routing
    graph.add_conditional_edges(
        "generate",
        should_retrieve,
        {
            "retrieve": "retrieve",
            "end": END,
        },
    )

    # After retrieval, go back to generate with context
    graph.add_edge("retrieve", "generate")

    # Compile the graph
    return graph.compile()


@lru_cache
def get_agent():
    """Get cached agent instance."""
    logger.info("initializing_agent")
    return create_agent_graph()
