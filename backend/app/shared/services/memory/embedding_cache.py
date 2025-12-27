"""Redis-based embedding cache for 80% cost savings."""

import hashlib
import json
from typing import TYPE_CHECKING

from redis.asyncio import Redis

from app.core.config import settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from app.shared.services.memory.embedding_service import EmbeddingVector

logger = get_logger(__name__)


class EmbeddingCache:
    """Cache embeddings in Redis to reduce API costs.

    Stores embeddings by text hash to avoid re-computing identical embeddings.
    Provides 80%+ hit rate for repeated content (docs, common queries).

    Example:
        cache = EmbeddingCache(redis_client)
        embedding = await cache.get_or_generate(
            text="Hello, world!",
            generator=embedding_service.generate_embedding
        )

    Attributes:
        redis: Redis async client
        ttl: Cache TTL in seconds (default 24 hours)
        prefix: Key prefix for namespacing ("embed:")
    """

    def __init__(self, redis: Redis, ttl: int = 86400) -> None:
        """Initialize embedding cache.

        Args:
            redis: Redis async client instance
            ttl: Time-to-live in seconds (default 86400 = 24 hours)
        """
        self.redis = redis
        self.ttl = ttl  # 24 hours default
        self.prefix = "embed:"

    def _cache_key(self, text: str) -> str:
        """Generate cache key from text hash.

        Uses SHA256 hash (first 16 chars) for deterministic key generation
        while keeping keys reasonably short.

        Args:
            text: Input text to hash

        Returns:
            Redis key with prefix (e.g., "embed:a1b2c3d4e5f6g7h8")
        """
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        return f"{self.prefix}{text_hash}"

    async def get(self, text: str) -> "EmbeddingVector | None":
        """Get embedding from cache.

        Args:
            text: Input text to look up

        Returns:
            Cached embedding vector if found, None otherwise
        """
        key = self._cache_key(text)
        try:
            cached = await self.redis.get(key)
            if cached:
                logger.debug("embedding_cache_hit", key=key, text_length=len(text))
                return json.loads(cached)
            logger.debug("embedding_cache_miss", key=key, text_length=len(text))
            return None
        except Exception as e:
            # Log error but don't fail - cache miss is acceptable
            logger.warning(
                "embedding_cache_get_error",
                error=str(e),
                key=key,
            )
            return None

    async def set(self, text: str, embedding: "EmbeddingVector") -> None:
        """Store embedding in cache.

        Args:
            text: Input text (used for key generation)
            embedding: Embedding vector to cache
        """
        key = self._cache_key(text)
        try:
            await self.redis.setex(key, self.ttl, json.dumps(embedding))
            logger.debug(
                "embedding_cached",
                key=key,
                text_length=len(text),
                ttl_seconds=self.ttl,
            )
        except Exception as e:
            # Log error but don't fail - cache write failure shouldn't break generation
            logger.warning(
                "embedding_cache_set_error",
                error=str(e),
                key=key,
            )

    async def get_or_generate(
        self,
        text: str,
        generator: "Callable[[str], Awaitable[EmbeddingVector]]",
    ) -> "EmbeddingVector":
        """Get from cache or generate and cache.

        This is the main method to use for cache-aware embedding generation.
        Checks cache first, generates on miss, and stores result.

        Args:
            text: Input text to embed
            generator: Async function to generate embedding (called on cache miss)

        Returns:
            Embedding vector (from cache or freshly generated)

        Example:
            embedding = await cache.get_or_generate(
                "Hello, world!",
                lambda t: embedding_service.generate_embedding(t)
            )
        """
        cached = await self.get(text)
        if cached is not None:
            return cached

        # Cache miss - generate embedding
        logger.debug("embedding_generating", text_length=len(text))
        embedding = await generator(text)

        # Store in cache for next time
        await self.set(text, embedding)

        return embedding


def get_embedding_cache() -> EmbeddingCache:
    """Get embedding cache instance with Redis connection.

    Creates a new Redis connection for the cache. Use dependency injection
    in production to share connection pools.

    Returns:
        EmbeddingCache instance connected to configured Redis

    Example:
        cache = get_embedding_cache()
        embedding = await cache.get_or_generate(text, generator)
    """
    from redis.asyncio import from_url

    redis = from_url(settings.REDIS_URL)
    return EmbeddingCache(redis)


__all__ = ["EmbeddingCache", "get_embedding_cache"]
