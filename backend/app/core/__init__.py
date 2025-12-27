"""Core application modules.

This package contains core infrastructure components:
- config: Application settings from environment variables
- logging: Structured logging with structlog
- langfuse_service: LLM observability with Langfuse
- tracing: Decorator-based tracing for LangGraph workflows
"""

from app.core.config import get_settings, settings

__all__ = [
    "get_settings",
    "settings",
]
