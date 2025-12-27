"""Circuit breakers for external services.

This module provides pre-configured circuit breakers for different external services
to prevent cascade failures. Uses the custom async-safe CircuitBreaker implementation
from app.core.resilience instead of pybreaker for better async support.
"""

from app.core.logging import get_logger
from app.core.resilience import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerOpenError

logger = get_logger(__name__)


# OpenAI API circuit breaker (for embeddings and direct API calls)
openai_breaker = CircuitBreaker(
    name="openai_api",
    config=CircuitBreakerConfig(
        failure_threshold=5,  # Allow more retries for embeddings
        success_threshold=2,
        timeout_seconds=60.0,
    ),
)

# LLM inference circuit breaker (for agent calls via LangGraph)
llm_breaker = CircuitBreaker(
    name="llm_inference",
    config=CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout_seconds=120.0,  # Longer timeout for LLM recovery
    ),
)

# Database circuit breaker (for heavy queries that might timeout)
db_query_breaker = CircuitBreaker(
    name="database_query",
    config=CircuitBreakerConfig(
        failure_threshold=10,  # More tolerant for DB issues
        success_threshold=3,
        timeout_seconds=30.0,  # Quick recovery for DB
    ),
)


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "openai_breaker",
    "llm_breaker",
    "db_query_breaker",
]
