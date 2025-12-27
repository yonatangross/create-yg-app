"""Simple usage statistics tracking with Redis."""

from datetime import UTC, datetime

from redis.asyncio import Redis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class UsageStats:
    """Track usage statistics in Redis.

    Provides simple counters for chat requests, token usage, embeddings,
    and memory operations. Statistics are stored with daily and total aggregations.

    Example:
        stats = UsageStats(redis)
        await stats.track_chat(conversation_id="123", tokens_in=100, tokens_out=200)
        summary = await stats.get_stats()

    Attributes:
        redis: Redis async client
        prefix: Key prefix for namespacing ("stats:")
    """

    def __init__(self, redis: Redis) -> None:
        """Initialize usage stats tracker.

        Args:
            redis: Redis async client instance
        """
        self.redis = redis
        self.prefix = "stats:"

    async def increment(self, metric: str, amount: int = 1) -> None:
        """Increment a counter metric.

        Args:
            metric: Metric name (will be prefixed with "stats:")
            amount: Amount to increment by (default: 1)
        """
        key = f"{self.prefix}{metric}"
        try:
            await self.redis.incrby(key, amount)
            logger.debug("stat_incremented", metric=metric, amount=amount)
        except Exception as e:
            # Don't fail if stats tracking fails
            logger.warning("stat_increment_failed", metric=metric, error=str(e))

    async def track_chat(self, conversation_id: str, tokens_in: int, tokens_out: int) -> None:
        """Track a chat request.

        Records total chat count, daily chat count, and token usage
        (both total and daily).

        Args:
            conversation_id: Conversation identifier
            tokens_in: Number of input tokens
            tokens_out: Number of output tokens
        """
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        try:
            pipe = self.redis.pipeline()
            pipe.incrby(f"{self.prefix}chats:total", 1)
            pipe.incrby(f"{self.prefix}chats:{today}", 1)
            pipe.incrby(f"{self.prefix}tokens:in:total", tokens_in)
            pipe.incrby(f"{self.prefix}tokens:out:total", tokens_out)
            pipe.incrby(f"{self.prefix}tokens:in:{today}", tokens_in)
            pipe.incrby(f"{self.prefix}tokens:out:{today}", tokens_out)
            await pipe.execute()
            logger.debug(
                "chat_tracked",
                conversation_id=conversation_id,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            )
        except Exception as e:
            logger.warning(
                "chat_tracking_failed",
                conversation_id=conversation_id,
                error=str(e),
            )

    async def track_embedding(self, tokens: int, cached: bool) -> None:
        """Track an embedding request.

        Records total embedding count, daily count, token usage,
        and cache hit/miss statistics.

        Args:
            tokens: Number of tokens processed
            cached: Whether the embedding was served from cache
        """
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        try:
            pipe = self.redis.pipeline()
            pipe.incrby(f"{self.prefix}embeddings:total", 1)
            pipe.incrby(f"{self.prefix}embeddings:{today}", 1)
            pipe.incrby(f"{self.prefix}embedding_tokens:total", tokens)
            if cached:
                pipe.incrby(f"{self.prefix}embeddings:cached:total", 1)
                pipe.incrby(f"{self.prefix}embeddings:cached:{today}", 1)
            await pipe.execute()
            logger.debug(
                "embedding_tracked",
                tokens=tokens,
                cached=cached,
            )
        except Exception as e:
            logger.warning(
                "embedding_tracking_failed",
                error=str(e),
            )

    async def track_memory_recall(self, count: int, latency_ms: float) -> None:
        """Track a memory recall operation.

        Records total recall count, items recalled, and cumulative latency.

        Args:
            count: Number of memory items recalled
            latency_ms: Latency in milliseconds
        """
        try:
            pipe = self.redis.pipeline()
            pipe.incrby(f"{self.prefix}memory:recalls:total", 1)
            pipe.incrby(f"{self.prefix}memory:items_recalled:total", count)
            pipe.incrbyfloat(f"{self.prefix}memory:latency_ms:total", latency_ms)
            await pipe.execute()
            logger.debug(
                "memory_recall_tracked",
                count=count,
                latency_ms=latency_ms,
            )
        except Exception as e:
            logger.warning(
                "memory_recall_tracking_failed",
                error=str(e),
            )

    async def get_stats(self) -> dict:
        """Get all statistics.

        Retrieves current statistics including chat counts, token usage,
        embedding statistics (with cache hit rate), and memory operations.

        Returns:
            Dictionary with statistics grouped by category:
            - chats: total and today's count
            - tokens: input/output totals
            - embeddings: total, cached, cache hit rate, tokens used
            - memory: recalls and items recalled
            - date: current date for "today" stats
        """
        today = datetime.now(UTC).strftime("%Y-%m-%d")

        # Get all stats keys
        keys = [
            f"{self.prefix}chats:total",
            f"{self.prefix}chats:{today}",
            f"{self.prefix}tokens:in:total",
            f"{self.prefix}tokens:out:total",
            f"{self.prefix}embeddings:total",
            f"{self.prefix}embeddings:cached:total",
            f"{self.prefix}embedding_tokens:total",
            f"{self.prefix}memory:recalls:total",
            f"{self.prefix}memory:items_recalled:total",
        ]

        try:
            values = await self.redis.mget(keys)

            # Calculate cache hit rate
            total_embeddings = int(values[4] or 0)
            cached_embeddings = int(values[5] or 0)
            cache_hit_rate = (
                (cached_embeddings / total_embeddings * 100) if total_embeddings > 0 else 0
            )

            return {
                "chats": {
                    "total": int(values[0] or 0),
                    "today": int(values[1] or 0),
                },
                "tokens": {
                    "input_total": int(values[2] or 0),
                    "output_total": int(values[3] or 0),
                },
                "embeddings": {
                    "total": total_embeddings,
                    "cached": cached_embeddings,
                    "cache_hit_rate": round(cache_hit_rate, 2),
                    "tokens_used": int(values[6] or 0),
                },
                "memory": {
                    "recalls": int(values[7] or 0),
                    "items_recalled": int(values[8] or 0),
                },
                "date": today,
            }
        except Exception as e:
            logger.error("get_stats_failed", error=str(e))
            # Return empty stats on error
            return {
                "chats": {"total": 0, "today": 0},
                "tokens": {"input_total": 0, "output_total": 0},
                "embeddings": {"total": 0, "cached": 0, "cache_hit_rate": 0.0, "tokens_used": 0},
                "memory": {"recalls": 0, "items_recalled": 0},
                "date": today,
            }

    async def reset_stats(self) -> int:
        """Reset all statistics.

        Deletes all stats keys from Redis. Use with caution.

        Returns:
            Count of keys deleted
        """
        try:
            keys = await self.redis.keys(f"{self.prefix}*")
            if keys:
                deleted = await self.redis.delete(*keys)
                logger.info("stats_reset", keys_deleted=deleted)
                return deleted
            return 0
        except Exception as e:
            logger.error("stats_reset_failed", error=str(e))
            return 0


def get_usage_stats() -> UsageStats:
    """Get usage stats instance.

    Creates a new Redis connection for stats tracking. Consider using
    dependency injection in production to share connection pools.

    Returns:
        UsageStats instance connected to configured Redis

    Example:
        stats = get_usage_stats()
        await stats.track_chat("conv_123", tokens_in=100, tokens_out=200)
    """
    from redis.asyncio import from_url

    redis = from_url(settings.REDIS_URL)
    return UsageStats(redis)


__all__ = ["UsageStats", "get_usage_stats"]
