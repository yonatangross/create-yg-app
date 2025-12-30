"""Langfuse tracing utilities for consistent instrumentation.

This module provides the robust_traceable decorator for instrumenting
LangGraph nodes, agents, and workflows with proper metadata, tags, and
span types for observability in Langfuse.

Usage:
    @robust_traceable(name="my_node", tags=["workflow", "node"])
    async def my_node(state: AgentState) -> dict:
        return {"result": "data"}
"""

from collections.abc import Awaitable, Callable
from typing import Any, Literal, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

SpanType = Literal["span", "generation", "agent", "tool"]

RUN_TYPE_TO_SPAN_TYPE: dict[str, SpanType] = {
    "chain": "span",
    "tool": "tool",
    "llm": "generation",
    "retriever": "span",
    "embedding": "span",
    "prompt": "span",
    "parser": "span",
    "agent": "agent",
}


def robust_traceable(
    name: str | None = None,
    run_type: str = "chain",
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Production-ready traceable wrapper for Langfuse instrumentation.

    Args:
        name: Name for the trace (defaults to function name)
        run_type: Run type ("chain", "tool", "llm", etc.)
        tags: List of tags for filtering traces
        metadata: Additional metadata to attach to trace

    Returns:
        Decorated function with tracing enabled

    """
    span_type: SpanType = RUN_TYPE_TO_SPAN_TYPE.get(run_type, "span")

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        func_name = getattr(func, "__name__", "unknown")
        trace_name = name if name is not None else func_name

        try:
            from langfuse import get_client, observe

            observed_func = observe(
                name=trace_name,
                as_type=span_type,
                capture_input=True,
                capture_output=True,
            )(func)

            if tags or metadata:
                import functools

                @functools.wraps(func)
                async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                    try:
                        langfuse = get_client()
                        if tags or metadata:
                            update_kwargs: dict[str, Any] = {}
                            if tags:
                                update_kwargs["tags"] = tags
                            if metadata:
                                update_kwargs["metadata"] = metadata
                            if update_kwargs:
                                langfuse.update_current_trace(**update_kwargs)
                    except Exception:  # noqa: S110 - tracing should never break the app
                        pass

                    return await observed_func(*args, **kwargs)

                return wrapper

            return observed_func

        except ImportError:
            return func

    return decorator


def update_current_trace(
    *,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
) -> None:
    """Update the current Langfuse trace with additional context."""
    try:
        from langfuse import get_client

        langfuse = get_client()

        update_kwargs: dict[str, Any] = {}
        if tags:
            update_kwargs["tags"] = tags
        if metadata:
            update_kwargs["metadata"] = metadata
        if user_id:
            update_kwargs["user_id"] = user_id
        if session_id:
            update_kwargs["session_id"] = session_id

        if update_kwargs:
            langfuse.update_current_trace(**update_kwargs)

    except ImportError:
        pass
    except Exception:  # noqa: S110 - tracing should never break the app
        pass


def get_current_trace_id() -> str | None:
    """Get the current Langfuse trace ID."""
    try:
        from langfuse import get_client

        langfuse = get_client()
        trace_id = langfuse.get_current_trace_id()
        return str(trace_id) if trace_id else None

    except ImportError:
        return None
    except Exception:
        return None


def traced_tool(
    name: str,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Trace tool invocations in Langfuse.

    Args:
        name: Name for the tool span
        tags: List of tags for filtering traces
        metadata: Additional metadata to attach

    Returns:
        Decorated async function with tool tracing enabled

    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        try:
            from langfuse import get_client, observe

            observed_func = observe(
                name=name,
                as_type="tool",
                capture_input=True,
                capture_output=True,
            )(func)

            if tags or metadata:
                import functools

                @functools.wraps(func)
                async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                    try:
                        langfuse = get_client()
                        update_kwargs: dict[str, Any] = {}
                        if tags:
                            update_kwargs["tags"] = tags
                        if metadata:
                            update_kwargs["metadata"] = metadata
                        if update_kwargs:
                            langfuse.update_current_span(**update_kwargs)
                    except Exception:  # noqa: S110 - tracing should never break the app
                        pass

                    return await observed_func(*args, **kwargs)

                return wrapper

            return observed_func

        except ImportError:
            return func

    return decorator


def update_current_observation(
    *,
    metadata: dict[str, Any] | None = None,
    output: Any | None = None,
    level: str | None = None,
    status_message: str | None = None,
) -> None:
    """Update the current Langfuse observation (span) with additional context."""
    try:
        from langfuse import get_client

        langfuse = get_client()

        update_kwargs: dict[str, Any] = {}
        if metadata:
            update_kwargs["metadata"] = metadata
        if output is not None:
            update_kwargs["output"] = output
        if level:
            update_kwargs["level"] = level
        if status_message:
            update_kwargs["status_message"] = status_message

        if update_kwargs:
            langfuse.update_current_span(**update_kwargs)

    except ImportError:
        pass
    except Exception:  # noqa: S110 - tracing should never break the app
        pass
