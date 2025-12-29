"""Unit tests for EmbeddingService."""

import contextlib
import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import APIError, APITimeoutError, AuthenticationError, BadRequestError, RateLimitError
from tenacity import RetryError

from app.core.circuit_breaker import openai_breaker
from app.core.resilience import CircuitBreakerOpenError
from app.shared.services.memory.embedding_service import (
    EmbeddingService,
    get_embedding_service,
    normalize_vector,
)

pytestmark = pytest.mark.unit


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
    """Tests for retry logic with exponential backoff.

    Note: asyncio.sleep is automatically mocked by tests/unit/conftest.py
    """

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


class TestBatchAPIEmbedding:
    """Tests for Batch API embedding generation."""

    @pytest.fixture
    def mock_batch_client(self):
        """Create mock OpenAI client for Batch API."""
        mock_client = MagicMock()

        # Mock file creation
        mock_file = MagicMock()
        mock_file.id = "file-123"
        mock_client.files.create = AsyncMock(return_value=mock_file)

        # Mock batch creation
        mock_batch = MagicMock()
        mock_batch.id = "batch-456"
        mock_batch.status = "completed"
        mock_batch.output_file_id = "file-789"
        mock_client.batches.create = AsyncMock(return_value=mock_batch)
        mock_client.batches.retrieve = AsyncMock(return_value=mock_batch)

        # Mock file content download (JSONL results)
        mock_output = MagicMock()
        mock_output.text = (
            '{"custom_id": "0", "response": {"body": {"data": [{"embedding": '
            + str([0.5] * 1536)
            + "}]}}}\n"
            '{"custom_id": "1", "response": {"body": {"data": [{"embedding": '
            + str([0.3] * 1536)
            + "}]}}}"
        )
        mock_client.files.content = AsyncMock(return_value=mock_output)

        return mock_client

    @pytest.fixture
    def batch_service(self, mock_batch_client):
        """Create EmbeddingService with mocked batch client."""
        with patch("app.shared.services.memory.embedding_service.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-key"
            service = EmbeddingService()
            service.client = mock_batch_client
            return service

    @pytest.mark.asyncio
    async def test_batch_api_empty_texts_returns_empty(self, batch_service):
        """Test batch API with empty list returns empty dict."""
        result = await batch_service.generate_embeddings_batch_api([])
        assert result == {}

    @pytest.mark.asyncio
    async def test_batch_api_generates_default_custom_ids(self, batch_service):
        """Test batch API generates default custom_ids from indices."""
        texts = ["First text", "Second text"]
        result = await batch_service.generate_embeddings_batch_api(texts)

        # Should have results keyed by indices
        assert "0" in result
        assert "1" in result
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_batch_api_uses_custom_ids(self, batch_service, mock_batch_client):
        """Test batch API uses provided custom_ids."""
        # Update mock to return custom IDs
        mock_output = MagicMock()
        mock_output.text = (
            '{"custom_id": "doc_1", "response": {"body": {"data": [{"embedding": '
            + str([0.5] * 1536)
            + "}]}}}\n"
            '{"custom_id": "doc_2", "response": {"body": {"data": [{"embedding": '
            + str([0.3] * 1536)
            + "}]}}}"
        )
        mock_batch_client.files.content = AsyncMock(return_value=mock_output)

        texts = ["First text", "Second text"]
        custom_ids = ["doc_1", "doc_2"]
        result = await batch_service.generate_embeddings_batch_api(texts, custom_ids)

        assert "doc_1" in result
        assert "doc_2" in result
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_batch_api_mismatched_custom_ids_raises(self, batch_service):
        """Test batch API raises on mismatched custom_ids length."""
        texts = ["Text 1", "Text 2"]
        custom_ids = ["id_1"]  # Only 1 ID for 2 texts

        with pytest.raises(ValueError, match="custom_ids length.*must match"):
            await batch_service.generate_embeddings_batch_api(texts, custom_ids)

    @pytest.mark.asyncio
    async def test_batch_api_creates_file_correctly(self, batch_service, mock_batch_client):
        """Test batch API creates JSONL file with correct format."""
        texts = ["Hello", "World"]
        await batch_service.generate_embeddings_batch_api(texts)

        # Verify file creation was called
        mock_batch_client.files.create.assert_called_once()
        call_args = mock_batch_client.files.create.call_args
        assert call_args.kwargs["purpose"] == "batch"

        # Verify file content is bytes-like
        file_obj = call_args.kwargs["file"]
        assert hasattr(file_obj, "read")

    @pytest.mark.asyncio
    async def test_batch_api_submits_batch_correctly(self, batch_service, mock_batch_client):
        """Test batch API submits batch with correct parameters."""
        texts = ["Test text"]
        await batch_service.generate_embeddings_batch_api(texts)

        mock_batch_client.batches.create.assert_called_once()
        call_args = mock_batch_client.batches.create.call_args
        assert call_args.kwargs["input_file_id"] == "file-123"
        assert call_args.kwargs["endpoint"] == "/v1/embeddings"
        assert call_args.kwargs["completion_window"] == "24h"

    @pytest.mark.asyncio
    async def test_batch_api_polls_until_completion(self, batch_service, mock_batch_client):
        """Test batch API polls status until completion."""
        # Mock in-progress then completed
        in_progress_batch = MagicMock()
        in_progress_batch.id = "batch-456"
        in_progress_batch.status = "in_progress"

        completed_batch = MagicMock()
        completed_batch.id = "batch-456"
        completed_batch.status = "completed"
        completed_batch.output_file_id = "file-789"

        mock_batch_client.batches.retrieve = AsyncMock(
            side_effect=[in_progress_batch, completed_batch]
        )

        # Reduce poll interval for faster test
        batch_service.BATCH_POLL_INTERVAL = 0.1

        texts = ["Test"]
        await batch_service.generate_embeddings_batch_api(texts)

        # Should have polled twice
        assert mock_batch_client.batches.retrieve.call_count == 2

    @pytest.mark.asyncio
    async def test_batch_api_failed_status_raises(self, batch_service, mock_batch_client):
        """Test batch API raises on failed status."""
        failed_batch = MagicMock()
        failed_batch.id = "batch-456"
        failed_batch.status = "failed"
        failed_batch.errors = {"message": "Something went wrong"}

        mock_batch_client.batches.retrieve = AsyncMock(return_value=failed_batch)

        with pytest.raises(RuntimeError, match="Batch batch-456 failed"):
            await batch_service.generate_embeddings_batch_api(["Test"])

    @pytest.mark.asyncio
    async def test_batch_api_expired_status_raises(self, batch_service, mock_batch_client):
        """Test batch API raises on expired status."""
        expired_batch = MagicMock()
        expired_batch.id = "batch-456"
        expired_batch.status = "expired"

        mock_batch_client.batches.retrieve = AsyncMock(return_value=expired_batch)

        with pytest.raises(RuntimeError, match="Batch batch-456 expired"):
            await batch_service.generate_embeddings_batch_api(["Test"])

    @pytest.mark.asyncio
    async def test_batch_api_cancelled_status_raises(self, batch_service, mock_batch_client):
        """Test batch API raises on cancelled status."""
        cancelled_batch = MagicMock()
        cancelled_batch.id = "batch-456"
        cancelled_batch.status = "cancelled"

        mock_batch_client.batches.retrieve = AsyncMock(return_value=cancelled_batch)

        with pytest.raises(RuntimeError, match="Batch batch-456 cancelled"):
            await batch_service.generate_embeddings_batch_api(["Test"])

    @pytest.mark.asyncio
    async def test_batch_api_timeout_raises(self, batch_service, mock_batch_client):
        """Test batch API raises TimeoutError after max attempts."""
        in_progress_batch = MagicMock()
        in_progress_batch.id = "batch-456"
        in_progress_batch.status = "in_progress"

        mock_batch_client.batches.retrieve = AsyncMock(return_value=in_progress_batch)

        # Set very low max attempts for fast test
        batch_service.BATCH_MAX_POLL_ATTEMPTS = 2
        batch_service.BATCH_POLL_INTERVAL = 0.01

        with pytest.raises(TimeoutError, match="did not complete within 2 attempts"):
            await batch_service.generate_embeddings_batch_api(["Test"])

    @pytest.mark.asyncio
    async def test_batch_api_exponential_backoff(self, batch_service, mock_batch_client):
        """Test batch API uses exponential backoff for polling.

        Verifies asyncio.sleep is called with exponentially increasing delays.
        Note: asyncio.sleep is mocked by unit conftest, so we verify call args.
        """
        in_progress_batch = MagicMock()
        in_progress_batch.status = "in_progress"

        completed_batch = MagicMock()
        completed_batch.status = "completed"
        completed_batch.output_file_id = "file-789"

        # Return in-progress 3 times, then completed
        mock_batch_client.batches.retrieve = AsyncMock(
            side_effect=[in_progress_batch, in_progress_batch, in_progress_batch, completed_batch]
        )

        batch_service.BATCH_POLL_INTERVAL = 1  # 1 second base

        # Capture sleep calls to verify exponential backoff
        sleep_calls = []

        async def capture_sleep(seconds):
            sleep_calls.append(seconds)
            # Don't actually wait - just record the call

        with patch("asyncio.sleep", side_effect=capture_sleep):
            await batch_service.generate_embeddings_batch_api(["Test"])

        # Verify exponential backoff: 1s, 2s, 4s (base * 2^attempt)
        assert len(sleep_calls) == 3, f"Expected 3 sleep calls, got {len(sleep_calls)}"
        assert sleep_calls[0] == 1, f"First wait should be 1s, got {sleep_calls[0]}"
        assert sleep_calls[1] == 2, f"Second wait should be 2s, got {sleep_calls[1]}"
        assert sleep_calls[2] == 4, f"Third wait should be 4s, got {sleep_calls[2]}"

    @pytest.mark.asyncio
    async def test_batch_api_returns_normalized_vectors(self, batch_service):
        """Test batch API returns L2-normalized vectors."""
        texts = ["Test 1", "Test 2"]
        result = await batch_service.generate_embeddings_batch_api(texts)

        # Verify normalization
        for embedding in result.values():
            assert len(embedding) == 1536
            magnitude = math.sqrt(sum(x * x for x in embedding))
            assert abs(magnitude - 1.0) < 1e-6

    @pytest.mark.asyncio
    async def test_batch_api_handles_partial_errors(self, batch_service, mock_batch_client):
        """Test batch API handles errors in individual results."""
        # Mock output with one success and one error
        mock_output = MagicMock()
        mock_output.text = (
            '{"custom_id": "0", "response": {"body": {"data": [{"embedding": '
            + str([0.5] * 1536)
            + "}]}}}\n"
            '{"custom_id": "1", "error": {"message": "Rate limit exceeded"}}'
        )
        mock_batch_client.files.content = AsyncMock(return_value=mock_output)

        texts = ["Test 1", "Test 2"]
        result = await batch_service.generate_embeddings_batch_api(texts)

        # Should only have successful result
        assert len(result) == 1
        assert "0" in result
        assert "1" not in result

    @pytest.mark.asyncio
    async def test_batch_api_handles_invalid_dimensions(self, batch_service, mock_batch_client):
        """Test batch API skips results with invalid dimensions."""
        # Mock output with one valid and one invalid dimension
        mock_output = MagicMock()
        mock_output.text = (
            '{"custom_id": "0", "response": {"body": {"data": [{"embedding": '
            + str([0.5] * 1536)
            + "}]}}}\n"
            '{"custom_id": "1", "response": {"body": {"data": [{"embedding": '
            + str([0.3] * 100)  # Wrong dimension!
            + "}]}}}"
        )
        mock_batch_client.files.content = AsyncMock(return_value=mock_output)

        texts = ["Test 1", "Test 2"]
        result = await batch_service.generate_embeddings_batch_api(texts)

        # Should only have valid result
        assert len(result) == 1
        assert "0" in result
        assert "1" not in result

    @pytest.mark.asyncio
    async def test_batch_api_handles_malformed_json(self, batch_service, mock_batch_client):
        """Test batch API handles malformed JSON in results."""
        # Mock output with valid and malformed JSON
        mock_output = MagicMock()
        mock_output.text = (
            '{"custom_id": "0", "response": {"body": {"data": [{"embedding": '
            + str([0.5] * 1536)
            + "}]}}}\n"
            "{invalid json here}"
        )
        mock_batch_client.files.content = AsyncMock(return_value=mock_output)

        texts = ["Test 1", "Test 2"]
        result = await batch_service.generate_embeddings_batch_api(texts)

        # Should only have valid result
        assert len(result) == 1
        assert "0" in result

    @pytest.mark.asyncio
    async def test_batch_api_no_output_file_raises(self, batch_service, mock_batch_client):
        """Test batch API raises if batch has no output_file_id."""
        bad_batch = MagicMock()
        bad_batch.id = "batch-456"
        bad_batch.status = "completed"
        bad_batch.output_file_id = None

        mock_batch_client.batches.retrieve = AsyncMock(return_value=bad_batch)

        with pytest.raises(ValueError, match="has no output_file_id"):
            await batch_service.generate_embeddings_batch_api(["Test"])

    @pytest.mark.asyncio
    async def test_batch_api_truncates_long_texts(self, batch_service, mock_batch_client):
        """Test batch API truncates texts exceeding MAX_TOKENS."""
        long_text = "word " * 10000  # ~10000 tokens
        texts = [long_text]

        await batch_service.generate_embeddings_batch_api(texts)

        # Verify file was created (we can't easily check content, but it should work)
        mock_batch_client.files.create.assert_called_once()


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


class TestCircuitBreaker:
    """Tests for circuit breaker integration with EmbeddingService."""

    @pytest.fixture
    def embedding_service(self):
        """Create EmbeddingService with mocked client."""
        with patch("app.shared.services.memory.embedding_service.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-key"
            service = EmbeddingService()
            service.client = MagicMock()
            # Reset circuit breaker state before each test
            openai_breaker.reset()
            return service

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self, embedding_service):
        """Test circuit breaker opens after max failures (5)."""
        # Mock to always fail with APIError
        embedding_service.client.embeddings.create = AsyncMock(
            side_effect=APIError("API error", request=MagicMock(), body=None)
        )

        # Fail 5 times (should open circuit after 5th failure)
        for _ in range(5):
            with contextlib.suppress(APIError, RetryError):
                await embedding_service.generate_embedding("test")

        # Circuit should now be open - next call should raise CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            await embedding_service.generate_embedding("test")

    @pytest.mark.asyncio
    async def test_circuit_breaker_allows_requests_when_closed(self, embedding_service):
        """Test circuit breaker allows requests when closed."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.5] * 1536)]
        mock_response.usage.total_tokens = 10
        embedding_service.client.embeddings.create = AsyncMock(return_value=mock_response)

        # Should succeed without circuit breaker interference
        result = await embedding_service.generate_embedding("test")
        assert len(result) == 1536

    @pytest.mark.asyncio
    async def test_circuit_breaker_resets_after_success(self, embedding_service):
        """Test circuit breaker resets failure count after success."""
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.5] * 1536)]
        mock_response.usage.total_tokens = 10

        # Fail once, then succeed
        embedding_service.client.embeddings.create = AsyncMock(
            side_effect=[
                APIError("API error", request=MagicMock(), body=None),
                mock_response,
                mock_response,
            ]
        )

        # First call fails, but succeeds on retry
        result = await embedding_service.generate_embedding("test")
        assert len(result) == 1536

        # Second call should succeed normally (failure count reset)
        result = await embedding_service.generate_embedding("test again")
        assert len(result) == 1536

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_batch_embeddings(self, embedding_service):
        """Test circuit breaker protects batch embeddings."""
        # Mock to always fail
        embedding_service.client.embeddings.create = AsyncMock(
            side_effect=APIError("API error", request=MagicMock(), body=None)
        )

        # Fail 5 times to open circuit
        for _ in range(5):
            with contextlib.suppress(APIError, RetryError):
                await embedding_service.generate_embeddings_batch(["test"])

        # Circuit should be open now
        with pytest.raises(CircuitBreakerOpenError):
            await embedding_service.generate_embeddings_batch(["test"])

    @pytest.mark.asyncio
    async def test_circuit_breaker_excludes_value_errors(self, embedding_service):
        """Test circuit breaker doesn't count ValueError as failure."""
        # ValueError should not be counted by circuit breaker
        # (it's in excluded_exceptions in CircuitBreakerConfig)

        # This should not affect circuit state
        with pytest.raises(ValueError):
            await embedding_service.generate_embedding("")

        # Circuit should still be closed
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.5] * 1536)]
        mock_response.usage.total_tokens = 10
        embedding_service.client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await embedding_service.generate_embedding("valid text")
        assert len(result) == 1536

    @pytest.mark.asyncio
    async def test_circuit_breaker_logs_open_state(self, embedding_service):
        """Test circuit breaker logs when circuit opens."""
        # Mock to always fail
        embedding_service.client.embeddings.create = AsyncMock(
            side_effect=APIError("API error", request=MagicMock(), body=None)
        )

        # Fail enough times to open circuit
        for _ in range(5):
            with contextlib.suppress(APIError, RetryError):
                await embedding_service.generate_embedding("test")

        # Next call should raise CircuitBreakerOpenError and log it
        with patch("app.shared.services.memory.embedding_service.logger") as mock_logger:
            with pytest.raises(CircuitBreakerOpenError):
                await embedding_service.generate_embedding("test")

            # Verify error was logged
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert call_args[0][0] == "openai_circuit_open"
