"""Unit tests for EmbeddingCache."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.shared.services.memory.embedding_cache import EmbeddingCache, get_embedding_cache

pytestmark = pytest.mark.unit


class TestEmbeddingCache:
    """Tests for EmbeddingCache."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = MagicMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        return redis

    @pytest.fixture
    def embedding_cache(self, mock_redis):
        """Create EmbeddingCache with mocked Redis."""
        return EmbeddingCache(mock_redis, ttl=3600)

    def test_cache_key_generation(self, embedding_cache):
        """Test cache key is deterministic and includes prefix."""
        text = "Hello, world!"
        key = embedding_cache._cache_key(text)

        assert key.startswith("embed:")
        assert len(key) == 22  # "embed:" (6) + hash (16)

        # Same text produces same key
        key2 = embedding_cache._cache_key(text)
        assert key == key2

        # Different text produces different key
        key3 = embedding_cache._cache_key("Different text")
        assert key != key3

    @pytest.mark.asyncio
    async def test_get_cache_miss(self, embedding_cache, mock_redis):
        """Test cache miss returns None."""
        mock_redis.get = AsyncMock(return_value=None)

        result = await embedding_cache.get("Test text")

        assert result is None
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cache_hit(self, embedding_cache, mock_redis):
        """Test cache hit returns embedding."""
        embedding = [0.1, 0.2, 0.3]
        mock_redis.get = AsyncMock(return_value=json.dumps(embedding))

        result = await embedding_cache.get("Test text")

        assert result == embedding
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_handles_redis_error(self, embedding_cache, mock_redis):
        """Test get handles Redis errors gracefully."""
        mock_redis.get = AsyncMock(side_effect=Exception("Redis error"))

        result = await embedding_cache.get("Test text")

        # Should return None on error, not raise
        assert result is None

    @pytest.mark.asyncio
    async def test_set_stores_embedding(self, embedding_cache, mock_redis):
        """Test set stores embedding in Redis."""
        text = "Test text"
        embedding = [0.1, 0.2, 0.3]

        await embedding_cache.set(text, embedding)

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 3600  # TTL
        assert json.loads(call_args[0][2]) == embedding

    @pytest.mark.asyncio
    async def test_set_handles_redis_error(self, embedding_cache, mock_redis):
        """Test set handles Redis errors gracefully."""
        mock_redis.setex = AsyncMock(side_effect=Exception("Redis error"))

        # Should not raise
        await embedding_cache.set("Test text", [0.1, 0.2])

        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_generate_cache_hit(self, embedding_cache, mock_redis):
        """Test get_or_generate returns cached value."""
        embedding = [0.1, 0.2, 0.3]
        mock_redis.get = AsyncMock(return_value=json.dumps(embedding))

        # Generator should NOT be called on cache hit
        generator = AsyncMock()

        result = await embedding_cache.get_or_generate("Test text", generator)

        assert result == embedding
        generator.assert_not_called()
        mock_redis.get.assert_called_once()
        mock_redis.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_generate_cache_miss(self, embedding_cache, mock_redis):
        """Test get_or_generate generates and caches on miss."""
        embedding = [0.1, 0.2, 0.3]
        mock_redis.get = AsyncMock(return_value=None)  # Cache miss

        # Generator should be called
        generator = AsyncMock(return_value=embedding)

        result = await embedding_cache.get_or_generate("Test text", generator)

        assert result == embedding
        generator.assert_called_once_with("Test text")
        mock_redis.get.assert_called_once()
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_generate_caches_result(self, embedding_cache, mock_redis):
        """Test get_or_generate stores generated embedding."""
        text = "Test text"
        embedding = [0.1, 0.2, 0.3]
        mock_redis.get = AsyncMock(return_value=None)

        generator = AsyncMock(return_value=embedding)

        await embedding_cache.get_or_generate(text, generator)

        # Verify setex was called with correct data
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert json.loads(call_args[0][2]) == embedding

    @pytest.mark.asyncio
    async def test_cache_with_large_embedding(self, embedding_cache, mock_redis):
        """Test caching with realistic embedding size (1536 dimensions)."""
        text = "Test text"
        embedding = [0.1] * 1536  # OpenAI text-embedding-3-small size
        mock_redis.get = AsyncMock(return_value=None)

        await embedding_cache.set(text, embedding)

        # Verify it was stored
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        stored_embedding = json.loads(call_args[0][2])
        assert len(stored_embedding) == 1536

    @pytest.mark.asyncio
    async def test_cache_with_unicode_text(self, embedding_cache, mock_redis):
        """Test cache handles unicode text correctly."""
        text = "Hello 世界 🌍"
        embedding = [0.1, 0.2, 0.3]

        # Test set
        await embedding_cache.set(text, embedding)
        mock_redis.setex.assert_called_once()

        # Test get
        mock_redis.get = AsyncMock(return_value=json.dumps(embedding))
        result = await embedding_cache.get(text)
        assert result == embedding

    def test_cache_ttl_configuration(self, mock_redis):
        """Test cache TTL is configurable."""
        cache1 = EmbeddingCache(mock_redis, ttl=7200)
        assert cache1.ttl == 7200

        cache2 = EmbeddingCache(mock_redis, ttl=3600)
        assert cache2.ttl == 3600

    def test_cache_key_prefix(self, embedding_cache):
        """Test cache keys have correct prefix."""
        key = embedding_cache._cache_key("test")
        assert key.startswith("embed:")


class TestGetEmbeddingCache:
    """Tests for get_embedding_cache factory."""

    @patch("redis.asyncio.from_url")
    @patch("app.shared.services.memory.embedding_cache.settings")
    def test_get_embedding_cache_creates_redis_connection(self, mock_settings, mock_from_url):
        """Test factory creates Redis connection from settings."""
        mock_settings.REDIS_URL = "redis://localhost:6390"
        mock_redis = MagicMock()
        mock_from_url.return_value = mock_redis

        cache = get_embedding_cache()

        mock_from_url.assert_called_once_with("redis://localhost:6390")
        assert isinstance(cache, EmbeddingCache)
        assert cache.redis == mock_redis

    @patch("redis.asyncio.from_url")
    @patch("app.shared.services.memory.embedding_cache.settings")
    def test_get_embedding_cache_default_ttl(self, mock_settings, mock_from_url):
        """Test factory uses default TTL (24 hours)."""
        mock_settings.REDIS_URL = "redis://localhost:6390"
        mock_from_url.return_value = MagicMock()

        cache = get_embedding_cache()

        assert cache.ttl == 86400  # 24 hours
