"""Unit tests for UsageStats."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.shared.services.stats.usage_stats import UsageStats, get_usage_stats


class TestUsageStats:
    """Tests for UsageStats."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = MagicMock()
        redis.incrby = AsyncMock()
        redis.incrbyfloat = AsyncMock()
        redis.mget = AsyncMock()
        redis.keys = AsyncMock()
        redis.delete = AsyncMock()
        redis.pipeline = MagicMock()
        return redis

    @pytest.fixture
    def usage_stats(self, mock_redis):
        """Create UsageStats with mocked Redis."""
        return UsageStats(mock_redis)

    @pytest.mark.asyncio
    async def test_increment_counter(self, usage_stats, mock_redis):
        """Test basic counter increment."""
        await usage_stats.increment("test_metric", 5)

        mock_redis.incrby.assert_called_once_with("stats:test_metric", 5)

    @pytest.mark.asyncio
    async def test_increment_default_amount(self, usage_stats, mock_redis):
        """Test increment with default amount of 1."""
        await usage_stats.increment("test_metric")

        mock_redis.incrby.assert_called_once_with("stats:test_metric", 1)

    @pytest.mark.asyncio
    async def test_increment_handles_redis_error(self, usage_stats, mock_redis):
        """Test increment handles Redis errors gracefully."""
        mock_redis.incrby = AsyncMock(side_effect=Exception("Redis error"))

        # Should not raise
        await usage_stats.increment("test_metric")

        mock_redis.incrby.assert_called_once()

    @pytest.mark.asyncio
    async def test_track_chat(self, usage_stats, mock_redis):
        """Test tracking chat request."""
        mock_pipe = MagicMock()
        mock_pipe.incrby = MagicMock()
        mock_pipe.execute = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipe

        await usage_stats.track_chat(
            conversation_id="conv_123",
            tokens_in=100,
            tokens_out=200,
        )

        # Verify pipeline was used
        mock_redis.pipeline.assert_called_once()
        mock_pipe.execute.assert_called_once()

        # Verify correct increments (6 total: 2 for chats, 4 for tokens)
        assert mock_pipe.incrby.call_count == 6

    @pytest.mark.asyncio
    async def test_track_chat_increments_correct_keys(self, usage_stats, mock_redis):
        """Test chat tracking increments all required keys."""
        mock_pipe = MagicMock()
        mock_pipe.incrby = MagicMock()
        mock_pipe.execute = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipe

        await usage_stats.track_chat(
            conversation_id="conv_123",
            tokens_in=100,
            tokens_out=200,
        )

        # Get all calls to incrby
        calls = [call[0] for call in mock_pipe.incrby.call_args_list]

        # Check that expected keys are incremented
        keys = [call[0] for call in calls]
        assert "stats:chats:total" in keys
        assert any("stats:chats:" in key for key in keys)  # Daily key
        assert "stats:tokens:in:total" in keys
        assert "stats:tokens:out:total" in keys

    @pytest.mark.asyncio
    async def test_track_chat_handles_redis_error(self, usage_stats, mock_redis):
        """Test chat tracking handles Redis errors gracefully."""
        mock_pipe = MagicMock()
        mock_pipe.execute = AsyncMock(side_effect=Exception("Redis error"))
        mock_redis.pipeline.return_value = mock_pipe

        # Should not raise
        await usage_stats.track_chat("conv_123", tokens_in=100, tokens_out=200)

    @pytest.mark.asyncio
    async def test_track_embedding_cached(self, usage_stats, mock_redis):
        """Test tracking cached embedding."""
        mock_pipe = MagicMock()
        mock_pipe.incrby = MagicMock()
        mock_pipe.execute = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipe

        await usage_stats.track_embedding(tokens=50, cached=True)

        # Verify pipeline was used
        mock_redis.pipeline.assert_called_once()
        mock_pipe.execute.assert_called_once()

        # Should increment cache counters (5 increments for cached)
        assert mock_pipe.incrby.call_count == 5

    @pytest.mark.asyncio
    async def test_track_embedding_not_cached(self, usage_stats, mock_redis):
        """Test tracking non-cached embedding."""
        mock_pipe = MagicMock()
        mock_pipe.incrby = MagicMock()
        mock_pipe.execute = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipe

        await usage_stats.track_embedding(tokens=50, cached=False)

        # Verify pipeline was used
        mock_redis.pipeline.assert_called_once()
        mock_pipe.execute.assert_called_once()

        # Should NOT increment cache counters (3 increments for non-cached)
        assert mock_pipe.incrby.call_count == 3

    @pytest.mark.asyncio
    async def test_track_embedding_handles_redis_error(self, usage_stats, mock_redis):
        """Test embedding tracking handles Redis errors gracefully."""
        mock_pipe = MagicMock()
        mock_pipe.execute = AsyncMock(side_effect=Exception("Redis error"))
        mock_redis.pipeline.return_value = mock_pipe

        # Should not raise
        await usage_stats.track_embedding(tokens=50, cached=True)

    @pytest.mark.asyncio
    async def test_track_memory_recall(self, usage_stats, mock_redis):
        """Test tracking memory recall operation."""
        mock_pipe = MagicMock()
        mock_pipe.incrby = MagicMock()
        mock_pipe.incrbyfloat = MagicMock()
        mock_pipe.execute = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipe

        await usage_stats.track_memory_recall(count=5, latency_ms=123.45)

        # Verify pipeline was used
        mock_redis.pipeline.assert_called_once()
        mock_pipe.execute.assert_called_once()

        # Should increment 3 counters (2 incrby, 1 incrbyfloat)
        assert mock_pipe.incrby.call_count == 2
        assert mock_pipe.incrbyfloat.call_count == 1

    @pytest.mark.asyncio
    async def test_track_memory_recall_increments_correct_keys(self, usage_stats, mock_redis):
        """Test memory recall tracking increments correct keys."""
        mock_pipe = MagicMock()
        mock_pipe.incrby = MagicMock()
        mock_pipe.incrbyfloat = MagicMock()
        mock_pipe.execute = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipe

        await usage_stats.track_memory_recall(count=5, latency_ms=123.45)

        # Check incrby calls
        incrby_calls = [call[0] for call in mock_pipe.incrby.call_args_list]
        keys = [call[0] for call in incrby_calls]
        assert "stats:memory:recalls:total" in keys
        assert "stats:memory:items_recalled:total" in keys

        # Check incrbyfloat call
        float_call = mock_pipe.incrbyfloat.call_args[0]
        assert float_call[0] == "stats:memory:latency_ms:total"
        assert float_call[1] == 123.45

    @pytest.mark.asyncio
    async def test_track_memory_recall_handles_redis_error(self, usage_stats, mock_redis):
        """Test memory recall tracking handles Redis errors gracefully."""
        mock_pipe = MagicMock()
        mock_pipe.execute = AsyncMock(side_effect=Exception("Redis error"))
        mock_redis.pipeline.return_value = mock_pipe

        # Should not raise
        await usage_stats.track_memory_recall(count=5, latency_ms=123.45)

    @pytest.mark.asyncio
    async def test_get_stats(self, usage_stats, mock_redis):
        """Test retrieving statistics."""
        # Mock mget to return stats values
        mock_redis.mget = AsyncMock(
            return_value=[
                b"100",  # chats:total
                b"10",  # chats:today
                b"5000",  # tokens:in:total
                b"8000",  # tokens:out:total
                b"200",  # embeddings:total
                b"160",  # embeddings:cached:total
                b"25000",  # embedding_tokens:total
                b"50",  # memory:recalls:total
                b"250",  # memory:items_recalled:total
            ]
        )

        stats = await usage_stats.get_stats()

        # Verify structure
        assert "chats" in stats
        assert "tokens" in stats
        assert "embeddings" in stats
        assert "memory" in stats
        assert "date" in stats

        # Verify values
        assert stats["chats"]["total"] == 100
        assert stats["chats"]["today"] == 10
        assert stats["tokens"]["input_total"] == 5000
        assert stats["tokens"]["output_total"] == 8000
        assert stats["embeddings"]["total"] == 200
        assert stats["embeddings"]["cached"] == 160
        assert stats["embeddings"]["cache_hit_rate"] == 80.0  # 160/200 * 100
        assert stats["embeddings"]["tokens_used"] == 25000
        assert stats["memory"]["recalls"] == 50
        assert stats["memory"]["items_recalled"] == 250

    @pytest.mark.asyncio
    async def test_get_stats_calculates_cache_hit_rate(self, usage_stats, mock_redis):
        """Test cache hit rate calculation."""
        mock_redis.mget = AsyncMock(
            return_value=[
                b"0",  # chats:total
                b"0",  # chats:today
                b"0",  # tokens:in:total
                b"0",  # tokens:out:total
                b"100",  # embeddings:total
                b"75",  # embeddings:cached:total
                b"0",  # embedding_tokens:total
                b"0",  # memory:recalls:total
                b"0",  # memory:items_recalled:total
            ]
        )

        stats = await usage_stats.get_stats()

        assert stats["embeddings"]["cache_hit_rate"] == 75.0

    @pytest.mark.asyncio
    async def test_get_stats_handles_zero_embeddings(self, usage_stats, mock_redis):
        """Test cache hit rate with zero embeddings."""
        mock_redis.mget = AsyncMock(return_value=[b"0"] * 9)

        stats = await usage_stats.get_stats()

        # Should not divide by zero
        assert stats["embeddings"]["cache_hit_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_stats_handles_none_values(self, usage_stats, mock_redis):
        """Test get_stats handles None values from Redis."""
        mock_redis.mget = AsyncMock(return_value=[None] * 9)

        stats = await usage_stats.get_stats()

        # All values should default to 0
        assert stats["chats"]["total"] == 0
        assert stats["tokens"]["input_total"] == 0
        assert stats["embeddings"]["total"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_handles_redis_error(self, usage_stats, mock_redis):
        """Test get_stats handles Redis errors gracefully."""
        mock_redis.mget = AsyncMock(side_effect=Exception("Redis error"))

        stats = await usage_stats.get_stats()

        # Should return empty stats on error
        assert stats["chats"]["total"] == 0
        assert stats["tokens"]["input_total"] == 0
        assert stats["embeddings"]["total"] == 0
        assert "date" in stats

    @pytest.mark.asyncio
    async def test_reset_stats(self, usage_stats, mock_redis):
        """Test resetting all statistics."""
        mock_redis.keys = AsyncMock(
            return_value=[
                "stats:chats:total",
                "stats:tokens:in:total",
                "stats:embeddings:total",
            ]
        )
        mock_redis.delete = AsyncMock(return_value=3)

        deleted = await usage_stats.reset_stats()

        assert deleted == 3
        mock_redis.keys.assert_called_once_with("stats:*")
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_stats_no_keys(self, usage_stats, mock_redis):
        """Test reset_stats when no keys exist."""
        mock_redis.keys = AsyncMock(return_value=[])

        deleted = await usage_stats.reset_stats()

        assert deleted == 0
        mock_redis.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_reset_stats_handles_redis_error(self, usage_stats, mock_redis):
        """Test reset_stats handles Redis errors gracefully."""
        mock_redis.keys = AsyncMock(side_effect=Exception("Redis error"))

        deleted = await usage_stats.reset_stats()

        assert deleted == 0

    def test_prefix_configuration(self, usage_stats):
        """Test stats key prefix is correct."""
        assert usage_stats.prefix == "stats:"

    @pytest.mark.asyncio
    async def test_date_format_in_stats(self, usage_stats, mock_redis):
        """Test that date is formatted correctly (YYYY-MM-DD)."""
        mock_redis.mget = AsyncMock(return_value=[b"0"] * 9)

        stats = await usage_stats.get_stats()

        # Date should be in ISO format
        date = stats["date"]
        assert len(date) == 10  # YYYY-MM-DD
        assert date.count("-") == 2

        # Should be valid date
        datetime.strptime(date, "%Y-%m-%d")


class TestGetUsageStats:
    """Tests for get_usage_stats factory."""

    @patch("redis.asyncio.from_url")
    @patch("app.shared.services.stats.usage_stats.settings")
    def test_get_usage_stats_creates_redis_connection(self, mock_settings, mock_from_url):
        """Test factory creates Redis connection from settings."""
        mock_settings.REDIS_URL = "redis://localhost:6390"
        mock_redis = MagicMock()
        mock_from_url.return_value = mock_redis

        stats = get_usage_stats()

        mock_from_url.assert_called_once_with("redis://localhost:6390")
        assert isinstance(stats, UsageStats)
        assert stats.redis == mock_redis

    @patch("redis.asyncio.from_url")
    @patch("app.shared.services.stats.usage_stats.settings")
    def test_get_usage_stats_uses_configured_redis_url(self, mock_settings, mock_from_url):
        """Test factory uses configured Redis URL."""
        mock_settings.REDIS_URL = "redis://custom-host:6379"
        mock_from_url.return_value = MagicMock()

        get_usage_stats()

        mock_from_url.assert_called_once_with("redis://custom-host:6379")
