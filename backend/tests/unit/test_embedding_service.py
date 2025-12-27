"""Unit tests for EmbeddingService."""

import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import APIError, APITimeoutError, AuthenticationError, BadRequestError, RateLimitError
from tenacity import RetryError

from app.shared.services.memory.embedding_service import (
    EmbeddingService,
    get_embedding_service,
    normalize_vector,
)


class TestNormalizeVector:
    """Tests for normalize_vector helper function."""

    def test_normalize_vector_basic(self):
        """Test basic L2 normalization."""
        vector = [3.0, 4.0]  # Magnitude = 5.0
        normalized = normalize_vector(vector)
        assert normalized == [0.6, 0.8]

    def test_normalize_vector_magnitude_one(self):
        """Test that normalized vector has magnitude ~1.0."""
        vector = [1.0, 2.0, 3.0, 4.0]
        normalized = normalize_vector(vector)
        magnitude = math.sqrt(sum(x * x for x in normalized))
        assert abs(magnitude - 1.0) < 1e-9

    def test_normalize_vector_zero_vector(self):
        """Test that zero vector returns zero vector."""
        vector = [0.0, 0.0, 0.0]
        normalized = normalize_vector(vector)
        assert normalized == [0.0, 0.0, 0.0]

    def test_normalize_vector_preserves_direction(self):
        """Test that normalization preserves vector direction."""
        vector = [5.0, 5.0]
        normalized = normalize_vector(vector)
        # Both components should be equal (45-degree angle)
        assert abs(normalized[0] - normalized[1]) < 1e-9


class TestEmbeddingService:
    """Tests for EmbeddingService."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create mock OpenAI client with unnormalized embeddings."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        # Use unnormalized vector to test L2 normalization
        mock_response.data = [MagicMock(embedding=[0.5] * 1536)]
        mock_response.usage.total_tokens = 10
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        return mock_client

    @pytest.fixture
    def embedding_service(self, mock_openai_client):
        """Create EmbeddingService with mocked client."""
        with patch("app.shared.services.memory.embedding_service.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-key"
            service = EmbeddingService()
            service.client = mock_openai_client
            return service

    def test_count_tokens(self, embedding_service):
        """Test token counting with tiktoken."""
        # "Hello, world!" is 4 tokens in cl100k_base encoding
        text = "Hello, world!"
        token_count = embedding_service.count_tokens(text)
        assert token_count == 4

    def test_count_tokens_long_text(self, embedding_service):
        """Test token counting for longer text."""
        # "The quick brown fox jumps over the lazy dog" is 9 tokens
        text = "The quick brown fox jumps over the lazy dog"
        token_count = embedding_service.count_tokens(text)
        assert token_count == 9

    def test_truncate_to_tokens_no_truncation(self, embedding_service):
        """Test truncation when text is below limit."""
        text = "Hello, world!"
        truncated = embedding_service.truncate_to_tokens(text, max_tokens=100)
        assert truncated == text

    def test_truncate_to_tokens_with_truncation(self, embedding_service):
        """Test truncation when text exceeds limit."""
        text = "The quick brown fox jumps over the lazy dog"
        # Truncate to 5 tokens (should be "The quick brown fox jumps")
        truncated = embedding_service.truncate_to_tokens(text, max_tokens=5)
        token_count = embedding_service.count_tokens(truncated)
        assert token_count <= 5
        assert len(truncated) < len(text)

    @pytest.mark.asyncio
    async def test_generate_embedding_returns_correct_dimensions(self, embedding_service):
        """Test that embedding has 1536 dimensions."""
        result = await embedding_service.generate_embedding("Hello, world!")

        assert len(result) == 1536
        assert all(isinstance(x, float) for x in result)

    @pytest.mark.asyncio
    async def test_generate_embedding_returns_normalized_vector(self, embedding_service):
        """Test that embedding is L2 normalized."""
        result = await embedding_service.generate_embedding("Test text")

        # Calculate magnitude (should be ~1.0 for normalized vector)
        magnitude = math.sqrt(sum(x * x for x in result))
        assert abs(magnitude - 1.0) < 1e-6

    @pytest.mark.asyncio
    async def test_generate_embedding_calls_openai(self, embedding_service, mock_openai_client):
        """Test that OpenAI API is called correctly."""
        await embedding_service.generate_embedding("Test text")

        mock_openai_client.embeddings.create.assert_called_once()
        call_args = mock_openai_client.embeddings.create.call_args
        assert call_args.kwargs["model"] == "text-embedding-3-small"
        assert call_args.kwargs["input"] == "Test text"

    @pytest.mark.asyncio
    async def test_generate_embedding_empty_text_raises(self, embedding_service):
        """Test that empty text raises ValueError."""
        with pytest.raises(ValueError, match="Cannot generate embedding for empty"):
            await embedding_service.generate_embedding("")

        with pytest.raises(ValueError, match="Cannot generate embedding for empty"):
            await embedding_service.generate_embedding("   ")

    @pytest.mark.asyncio
    async def test_generate_embedding_truncates_long_text(
        self, embedding_service, mock_openai_client
    ):
        """Test that long text is truncated using token-based truncation."""
        # Create text longer than MAX_TOKENS (8000)
        long_text = "word " * 10000  # ~10000 tokens

        await embedding_service.generate_embedding(long_text)

        call_args = mock_openai_client.embeddings.create.call_args
        input_text = call_args.kwargs["input"]
        # Should be truncated to MAX_TOKENS (8000)
        token_count = embedding_service.count_tokens(input_text)
        assert token_count <= embedding_service.MAX_TOKENS

    @pytest.mark.asyncio
    async def test_generate_embedding_validates_dimensions(self, embedding_service):
        """Test that wrong dimensions raise ValueError."""
        # Mock response with wrong dimensions
        wrong_dim_response = MagicMock()
        wrong_dim_response.data = [MagicMock(embedding=[0.1] * 100)]  # Wrong!
        wrong_dim_response.usage.total_tokens = 10
        embedding_service.client.embeddings.create = AsyncMock(return_value=wrong_dim_response)

        with pytest.raises(ValueError, match="Expected 1536 dimensions"):
            await embedding_service.generate_embedding("Test")

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_empty_list(self, embedding_service):
        """Test batch embedding with empty list returns empty."""
        result = await embedding_service.generate_embeddings_batch([])
        assert result == []

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_multiple_texts(
        self, embedding_service, mock_openai_client
    ):
        """Test batch embedding processes multiple texts and normalizes them."""
        # Setup mock to return multiple unnormalized embeddings
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.5] * 1536),
            MagicMock(embedding=[0.3] * 1536),
        ]
        mock_openai_client.embeddings.create = AsyncMock(return_value=mock_response)

        texts = ["First text", "Second text"]
        result = await embedding_service.generate_embeddings_batch(texts)

        assert len(result) == 2
        assert len(result[0]) == 1536
        assert len(result[1]) == 1536

        # Verify both embeddings are normalized
        for embedding in result:
            magnitude = math.sqrt(sum(x * x for x in embedding))
            assert abs(magnitude - 1.0) < 1e-6


class TestEmbeddingServiceRetry:
    """Tests for retry logic with exponential backoff."""

    @pytest.fixture
    def embedding_service(self):
        """Create EmbeddingService with mocked client."""
        with patch("app.shared.services.memory.embedding_service.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-key"
            service = EmbeddingService()
            service.client = MagicMock()
            return service

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit_then_success(self, embedding_service):
        """Test successful retry after RateLimitError."""
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.5] * 1536)]
        mock_response.usage.total_tokens = 10

        # First call raises RateLimitError, second succeeds
        embedding_service.client.embeddings.create = AsyncMock(
            side_effect=[
                RateLimitError("Rate limit exceeded", response=MagicMock(), body=None),
                mock_response,
            ]
        )

        result = await embedding_service.generate_embedding("Test text")

        # Should succeed after retry
        assert len(result) == 1536
        assert embedding_service.client.embeddings.create.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_api_error_then_success(self, embedding_service):
        """Test successful retry after APIError."""
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.5] * 1536)]
        mock_response.usage.total_tokens = 10

        # First call raises APIError, second succeeds
        embedding_service.client.embeddings.create = AsyncMock(
            side_effect=[
                APIError("API error", request=MagicMock(), body=None),
                mock_response,
            ]
        )

        result = await embedding_service.generate_embedding("Test text")

        assert len(result) == 1536
        assert embedding_service.client.embeddings.create.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_timeout_then_success(self, embedding_service):
        """Test successful retry after APITimeoutError."""
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.5] * 1536)]
        mock_response.usage.total_tokens = 10

        # First call raises APITimeoutError, second succeeds
        embedding_service.client.embeddings.create = AsyncMock(
            side_effect=[
                APITimeoutError(request=MagicMock()),
                mock_response,
            ]
        )

        result = await embedding_service.generate_embedding("Test text")

        assert len(result) == 1536
        assert embedding_service.client.embeddings.create.call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, embedding_service):
        """Test that max retries (3) is respected."""
        # All calls raise RateLimitError
        embedding_service.client.embeddings.create = AsyncMock(
            side_effect=RateLimitError("Rate limit exceeded", response=MagicMock(), body=None)
        )

        with pytest.raises((RateLimitError, RetryError)):
            await embedding_service.generate_embedding("Test text")

        # Should attempt 3 times (initial + 2 retries)
        assert embedding_service.client.embeddings.create.call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_authentication_error(self, embedding_service):
        """Test that AuthenticationError is not retried."""
        embedding_service.client.embeddings.create = AsyncMock(
            side_effect=AuthenticationError("Invalid API key", response=MagicMock(), body=None)
        )

        with pytest.raises(AuthenticationError):
            await embedding_service.generate_embedding("Test text")

        # Should fail immediately without retry
        assert embedding_service.client.embeddings.create.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_bad_request_error(self, embedding_service):
        """Test that BadRequestError is not retried."""
        embedding_service.client.embeddings.create = AsyncMock(
            side_effect=BadRequestError("Invalid request", response=MagicMock(), body=None)
        )

        with pytest.raises(BadRequestError):
            await embedding_service.generate_embedding("Test text")

        # Should fail immediately without retry
        assert embedding_service.client.embeddings.create.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_multiple_failures_then_success(self, embedding_service):
        """Test retry after multiple transient failures."""
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.5] * 1536)]
        mock_response.usage.total_tokens = 10

        # Two failures, then success
        embedding_service.client.embeddings.create = AsyncMock(
            side_effect=[
                RateLimitError("Rate limit", response=MagicMock(), body=None),
                APITimeoutError(request=MagicMock()),
                mock_response,
            ]
        )

        result = await embedding_service.generate_embedding("Test text")

        assert len(result) == 1536
        assert embedding_service.client.embeddings.create.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_retry_on_rate_limit(self, embedding_service):
        """Test batch embedding retry logic."""
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.5] * 1536),
            MagicMock(embedding=[0.3] * 1536),
        ]

        # First call raises RateLimitError, second succeeds
        embedding_service.client.embeddings.create = AsyncMock(
            side_effect=[
                RateLimitError("Rate limit exceeded", response=MagicMock(), body=None),
                mock_response,
            ]
        )

        texts = ["First text", "Second text"]
        result = await embedding_service.generate_embeddings_batch(texts)

        assert len(result) == 2
        assert embedding_service.client.embeddings.create.call_count == 2


class TestGetEmbeddingService:
    """Tests for get_embedding_service factory."""

    def test_get_embedding_service_caches_instance(self):
        """Test that factory returns cached singleton."""
        with patch("app.shared.services.memory.embedding_service.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-key"

            # Clear cache first
            get_embedding_service.cache_clear()

            service1 = get_embedding_service()
            service2 = get_embedding_service()

            assert service1 is service2

    def test_get_embedding_service_raises_without_api_key(self):
        """Test that missing API key raises ValueError."""
        with patch("app.shared.services.memory.embedding_service.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None

            get_embedding_service.cache_clear()

            with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
                get_embedding_service()
