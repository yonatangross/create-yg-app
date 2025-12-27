"""Redis caching service for LLM optimization.

This module provides centralized Redis cache management for YG Starter:
- RedisSemanticCache: Vector similarity caching for LLM responses
- RedisCache: Exact-match caching for deterministic operations
- RedisChatMessageHistory: Tutor session chat history with search

Architecture:
- Uses langchain-redis v0.2.5 for seamless LangChain integration
- OpenAI embeddings (text-embedding-3-small) for semantic similarity
- Connection pooling via singleton pattern
- Automatic TTL expiration for all cache entries

Usage:
    >>> from app.shared.services.cache.redis_service import (
    ...     get_semantic_cache,
    ...     get_exact_cache,
    ...     get_chat_history,
    ... )
    >>> # For LLM calls - semantic similarity matching
    >>> semantic_cache = get_semantic_cache()
    >>> # For supervisor routing - exact content matching
    >>> exact_cache = get_exact_cache()
    >>> # For tutor chat sessions
    >>> history = get_chat_history("session_123")

Performance Targets:
- Cache hit latency: < 10ms P95
- Semantic cache hit rate: 40-70% (similar content)
- Memory usage: ~1MB per 10K cached responses
"""

from functools import lru_cache
from typing import TYPE_CHECKING

import structlog
from langchain_openai import OpenAIEmbeddings
from langchain_redis import RedisCache, RedisChatMessageHistory, RedisSemanticCache
from pydantic import SecretStr

from app.core.config import settings

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings

logger = structlog.get_logger(__name__)

# Constants for logging
_SESSION_ID_TRUNCATE_LENGTH = 8


@lru_cache(maxsize=1)
def _get_embedding_model() -> "Embeddings":
    """Get OpenAI embeddings model for semantic cache.

    Uses text-embedding-3-small (1536 dimensions) - same as EmbeddingService.
    Singleton pattern ensures one embedding client per process.

    Returns:
        OpenAIEmbeddings instance configured for text-embedding-3-small.

    Raises:
        ValueError: If OPENAI_API_KEY is not configured.

    """
    if not settings.OPENAI_API_KEY:
        msg = "OPENAI_API_KEY is required for semantic caching"
        raise ValueError(msg)

    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=SecretStr(settings.OPENAI_API_KEY),
    )


@lru_cache(maxsize=1)
def get_semantic_cache() -> RedisSemanticCache:
    """Get semantic cache for LLM response caching.

    Uses vector similarity to return cached responses for semantically
    similar queries. Ideal for agent analysis where similar content
    produces similar outputs.

    Cache behavior:
    - distance_threshold=0.08 means ~92% similarity required for hit
    - TTL from settings (default 24 hours)
    - Embeddings via OpenAI text-embedding-3-small

    Returns:
        RedisSemanticCache configured for LLM response caching.

    Example:
        >>> cache = get_semantic_cache()
        >>> # Use with LangChain LLM
        >>> llm = ChatAnthropic(cache=cache)

    """
    logger.info(
        "semantic_cache_initializing",
        redis_url=settings.REDIS_URL.split("@")[-1],  # Hide credentials
        ttl=settings.REDIS_SEMANTIC_CACHE_TTL,
        threshold=settings.REDIS_SIMILARITY_THRESHOLD,
    )

    return RedisSemanticCache(
        embeddings=_get_embedding_model(),
        redis_url=settings.REDIS_URL,
        distance_threshold=settings.REDIS_SIMILARITY_THRESHOLD,
        ttl=settings.REDIS_SEMANTIC_CACHE_TTL,
    )


@lru_cache(maxsize=1)
def get_exact_cache() -> RedisCache:
    """Get exact-match cache for deterministic operations.

    Used for supervisor routing where identical content should always
    route to the same agents. No semantic matching - exact key match only.

    Cache behavior:
    - Exact string match on cache key
    - TTL from settings (default 1 hour)
    - Lower TTL because routing decisions may need to evolve

    Returns:
        RedisCache configured for exact-match caching.

    Example:
        >>> cache = get_exact_cache()
        >>> # Cache key is hash of content
        >>> key = hashlib.sha256(content.encode()).hexdigest()

    """
    logger.info(
        "exact_cache_initializing",
        redis_url=settings.REDIS_URL.split("@")[-1],
        ttl=settings.REDIS_EXACT_CACHE_TTL,
    )

    return RedisCache(
        redis_url=settings.REDIS_URL,
        ttl=settings.REDIS_EXACT_CACHE_TTL,
    )


def get_chat_history(session_id: str, ttl: int | None = None) -> RedisChatMessageHistory:
    """Get chat history for a tutor session.

    Creates a new RedisChatMessageHistory instance for each session.
    NOT cached because each session needs its own history instance.

    Features:
    - Full-text search across messages
    - Automatic TTL expiration
    - Chronological message retrieval
    - Session isolation via key prefix

    Args:
        session_id: Unique session identifier (e.g., UUID string)
        ttl: Optional TTL override in seconds (default from settings)

    Returns:
        RedisChatMessageHistory instance for the session.

    Example:
        >>> history = get_chat_history("tutor_session_abc123")
        >>> history.add_message(HumanMessage(content="How do I use FastAPI?"))
        >>> history.add_message(AIMessage(content="FastAPI is a modern..."))
        >>> # Full-text search
        >>> results = history.search_messages("FastAPI", limit=5)

    """
    effective_ttl = ttl if ttl is not None else settings.REDIS_CHAT_HISTORY_TTL

    logger.debug(
        "chat_history_creating",
        session_id=session_id[:_SESSION_ID_TRUNCATE_LENGTH] + "..."
        if len(session_id) > _SESSION_ID_TRUNCATE_LENGTH
        else session_id,
        ttl=effective_ttl,
    )

    return RedisChatMessageHistory(
        session_id=session_id,
        redis_url=settings.REDIS_URL,
        ttl=effective_ttl,
        key_prefix="yg-starter:chat:",
    )


def clear_all_caches() -> None:
    """Clear all cached instances.

    Call this when configuration changes or during testing.
    Does NOT clear Redis data - only clears Python singleton instances.
    """
    _get_embedding_model.cache_clear()
    get_semantic_cache.cache_clear()
    get_exact_cache.cache_clear()
    logger.info("cache_instances_cleared")
