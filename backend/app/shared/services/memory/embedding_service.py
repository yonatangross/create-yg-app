"""Embedding generation service using OpenAI text-embedding-3-small."""

import asyncio
import io
import json
import logging
import math
from functools import lru_cache
from typing import Any

import tiktoken
from openai import (
    APIError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)
# Get standard logger for tenacity's before_sleep_log (it doesn't support structlog)
_stdlib_logger = logging.getLogger(__name__)


# Custom retry condition: only retry transient errors
def _should_retry_on_exception(exception: BaseException) -> bool:
    """Determine if an exception should trigger a retry.

    Only retry on transient errors (rate limits, timeouts, general API errors).
    Do NOT retry on permanent errors (auth failures, invalid requests).

    Args:
        exception: The exception that was raised.

    Returns:
        True if the exception should trigger a retry, False otherwise.
    """
    # Don't retry auth or validation errors (these won't fix themselves)
    if isinstance(exception, (AuthenticationError, BadRequestError)):
        return False
    # Retry transient errors
    return isinstance(exception, (RateLimitError, APITimeoutError, APIError))


# Type alias for embedding vectors
EmbeddingVector = list[float]


def normalize_vector(vector: list[float]) -> list[float]:
    """L2 normalize vector for optimal cosine similarity with pgvector.

    Args:
        vector: Input vector to normalize.

    Returns:
        L2-normalized vector with magnitude ~1.0.
    """
    norm = math.sqrt(sum(x * x for x in vector))
    return [x / norm for x in vector] if norm > 0 else vector


class EmbeddingService:
    """Generate embeddings via OpenAI text-embedding-3-small.

    Produces 1536-dimensional L2-normalized vectors optimized for semantic similarity search.
    Uses tiktoken for accurate token counting and truncation.

    Attributes:
        model: The OpenAI embedding model to use.
        dimensions: The output vector dimensions (1536).
        encoding: Tiktoken encoding for token counting.

    Example:
        service = EmbeddingService()
        embedding = await service.generate_embedding("Hello, world!")
        # embedding is a list of 1536 L2-normalized floats
    """

    MAX_TOKENS = 8000  # Below 8191 API limit with safety margin
    BATCH_COMPLETION_WINDOW = "24h"  # Batch API completion window
    BATCH_POLL_INTERVAL = 60  # Initial poll interval in seconds
    BATCH_MAX_POLL_ATTEMPTS = 1440  # 24 hours at 1 min intervals

    def __init__(self) -> None:
        """Initialize the embedding service."""
        if not settings.OPENAI_API_KEY:
            msg = "OPENAI_API_KEY is required for embeddings"
            raise ValueError(msg)

        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "text-embedding-3-small"
        self.dimensions = 1536
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken.

        Args:
            text: Input text to count tokens for.

        Returns:
            Number of tokens in the text.
        """
        return len(self.encoding.encode(text))

    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to max tokens using tiktoken.

        Args:
            text: Input text to truncate.
            max_tokens: Maximum number of tokens to keep.

        Returns:
            Truncated text that fits within max_tokens.
        """
        tokens = self.encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return self.encoding.decode(tokens[:max_tokens])

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=1, max=32),
        retry=retry_if_exception(_should_retry_on_exception),
        before_sleep=before_sleep_log(_stdlib_logger, logging.WARNING),
    )
    async def generate_embedding(self, text: str) -> EmbeddingVector:
        """Generate a 1536-dimensional L2-normalized embedding vector.

        Retries up to 3 times with exponential backoff (1s -> 2s -> 4s -> 8s -> 16s -> 32s)
        on transient errors (RateLimitError, APIError, APITimeoutError).

        Args:
            text: The input text to embed. Truncated to MAX_TOKENS (8000) tokens.

        Returns:
            A list of 1536 L2-normalized floats representing the semantic embedding.

        Raises:
            ValueError: If text is empty.
            RateLimitError: If rate limit exceeded after retries.
            APIError: If API error persists after retries.
            APITimeoutError: If timeout persists after retries.
            AuthenticationError: If API key is invalid (no retry).
            BadRequestError: If request is malformed (no retry).
        """
        if not text or not text.strip():
            msg = "Cannot generate embedding for empty text"
            raise ValueError(msg)

        # Use token-based truncation instead of character estimate
        token_count = self.count_tokens(text)
        truncated = (
            self.truncate_to_tokens(text, self.MAX_TOKENS)
            if token_count > self.MAX_TOKENS
            else text
        )

        logger.debug(
            "generating_embedding",
            text_length=len(text),
            token_count=token_count,
            truncated=token_count > self.MAX_TOKENS,
        )

        response = await self.client.embeddings.create(
            model=self.model,
            input=truncated,
        )

        embedding = response.data[0].embedding

        # Validate dimensions
        if len(embedding) != self.dimensions:
            msg = f"Expected {self.dimensions} dimensions, got {len(embedding)}"
            raise ValueError(msg)

        # Apply L2 normalization for optimal pgvector cosine similarity
        normalized_embedding = normalize_vector(embedding)

        logger.debug(
            "embedding_generated",
            dimensions=len(normalized_embedding),
            usage_tokens=response.usage.total_tokens,
        )

        return normalized_embedding

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=1, max=32),
        retry=retry_if_exception(_should_retry_on_exception),
        before_sleep=before_sleep_log(_stdlib_logger, logging.WARNING),
    )
    async def generate_embeddings_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[EmbeddingVector]:
        """Generate L2-normalized embeddings for multiple texts.

        Processes texts in batches for efficiency. Retries up to 3 times with
        exponential backoff on transient errors (RateLimitError, APIError, APITimeoutError).

        Args:
            texts: List of texts to embed.
            batch_size: Number of texts per API call (max 2048).

        Returns:
            List of L2-normalized embedding vectors in the same order as input.

        Raises:
            RateLimitError: If rate limit exceeded after retries.
            APIError: If API error persists after retries.
            APITimeoutError: If timeout persists after retries.
        """
        if not texts:
            return []

        all_embeddings: list[EmbeddingVector] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            # Use token-based truncation for each text
            truncated_batch = [
                self.truncate_to_tokens(t, self.MAX_TOKENS)
                if self.count_tokens(t) > self.MAX_TOKENS
                else t
                for t in batch
            ]

            response = await self.client.embeddings.create(
                model=self.model,
                input=truncated_batch,
            )

            # Extract embeddings and apply L2 normalization
            batch_embeddings = [normalize_vector(d.embedding) for d in response.data]
            all_embeddings.extend(batch_embeddings)

            logger.debug(
                "batch_embeddings_generated",
                batch_index=i // batch_size,
                batch_size=len(batch),
            )

        return all_embeddings

    async def generate_embeddings_batch_api(
        self,
        texts: list[str],
        custom_ids: list[str] | None = None,
    ) -> dict[str, list[float]]:
        """Generate embeddings using Batch API (50% cost savings).

        Use for non-time-sensitive operations like:
        - Document ingestion
        - Memory consolidation
        - Bulk imports

        The Batch API provides 50% cost savings but may take up to 24 hours to complete.
        For urgent embedding needs, use generate_embedding() or generate_embeddings_batch().

        Args:
            texts: List of texts to embed (max 50,000 per batch).
            custom_ids: Optional custom IDs for tracking (defaults to indices).

        Returns:
            Dict mapping custom_id to L2-normalized embedding vector.

        Raises:
            ValueError: If texts is empty or custom_ids length mismatches.
            RuntimeError: If batch fails, expires, or is cancelled.
            TimeoutError: If batch does not complete within 24 hours.
        """
        if not texts:
            return {}

        if custom_ids and len(custom_ids) != len(texts):
            msg = f"custom_ids length ({len(custom_ids)}) must match texts length ({len(texts)})"
            raise ValueError(msg)

        custom_ids = custom_ids or [str(i) for i in range(len(texts))]

        logger.info(
            "batch_api_starting",
            text_count=len(texts),
            estimated_completion="24h",
        )

        # 1. Create batch file (JSONL)
        batch_file = await self._create_batch_file(texts, custom_ids)

        # 2. Submit batch
        batch = await self.client.batches.create(
            input_file_id=batch_file.id,
            endpoint="/v1/embeddings",
            completion_window=self.BATCH_COMPLETION_WINDOW,
        )

        logger.info(
            "batch_submitted",
            batch_id=batch.id,
            text_count=len(texts),
            input_file_id=batch_file.id,
        )

        # 3. Poll for completion
        completed_batch = await self._poll_batch_completion(batch.id)

        # 4. Download and parse results
        results = await self._download_batch_results(completed_batch)

        logger.info(
            "batch_completed",
            batch_id=batch.id,
            result_count=len(results),
        )

        return results

    async def _create_batch_file(
        self,
        texts: list[str],
        custom_ids: list[str],
    ) -> Any:
        """Create JSONL batch file for OpenAI Batch API.

        Args:
            texts: List of texts to embed.
            custom_ids: List of custom IDs for tracking.

        Returns:
            OpenAI FileObject with uploaded batch file.
        """
        lines = []
        for custom_id, text in zip(custom_ids, texts, strict=True):
            # Truncate text to token limit
            truncated = self.truncate_to_tokens(text, self.MAX_TOKENS)
            lines.append(
                json.dumps(
                    {
                        "custom_id": custom_id,
                        "method": "POST",
                        "url": "/v1/embeddings",
                        "body": {
                            "model": self.model,
                            "input": truncated,
                        },
                    }
                )
            )

        content = "\n".join(lines)

        logger.debug(
            "batch_file_created",
            line_count=len(lines),
            size_bytes=len(content),
        )

        # Create file-like object from string content
        file_content = io.BytesIO(content.encode("utf-8"))
        file_content.name = "batch_embeddings.jsonl"

        return await self.client.files.create(
            file=file_content,
            purpose="batch",
        )

    async def _poll_batch_completion(self, batch_id: str) -> Any:
        """Poll batch status until completion with exponential backoff.

        Args:
            batch_id: The batch ID to poll.

        Returns:
            Completed batch object.

        Raises:
            RuntimeError: If batch fails, expires, or is cancelled.
            TimeoutError: If batch does not complete within max attempts.
        """
        for attempt in range(self.BATCH_MAX_POLL_ATTEMPTS):
            batch = await self.client.batches.retrieve(batch_id)

            if batch.status == "completed":
                logger.info(
                    "batch_poll_completed",
                    batch_id=batch_id,
                    attempts=attempt + 1,
                )
                return batch
            elif batch.status in ("failed", "expired", "cancelled"):
                error_msg = f"Batch {batch_id} {batch.status}"
                if hasattr(batch, "errors") and batch.errors:
                    error_msg += f": {batch.errors}"
                logger.error(
                    "batch_poll_failed",
                    batch_id=batch_id,
                    status=batch.status,
                    errors=getattr(batch, "errors", None),
                )
                raise RuntimeError(error_msg)

            # Exponential backoff: 60s, 120s, 240s, 480s, capped at 5min (300s)
            wait_time = min(self.BATCH_POLL_INTERVAL * (2 ** min(attempt, 4)), 300)

            logger.debug(
                "batch_poll_waiting",
                batch_id=batch_id,
                attempt=attempt + 1,
                status=batch.status,
                wait_time_seconds=wait_time,
            )

            await asyncio.sleep(wait_time)

        error_msg = (
            f"Batch {batch_id} did not complete within {self.BATCH_MAX_POLL_ATTEMPTS} attempts"
        )
        logger.error("batch_poll_timeout", batch_id=batch_id)
        raise TimeoutError(error_msg)

    async def _download_batch_results(self, batch: Any) -> dict[str, list[float]]:
        """Download and parse batch results.

        Args:
            batch: Completed batch object with output_file_id.

        Returns:
            Dict mapping custom_id to L2-normalized embedding vector.

        Raises:
            ValueError: If batch has no output_file_id or results are malformed.
        """
        if not hasattr(batch, "output_file_id") or not batch.output_file_id:
            msg = f"Batch {batch.id} has no output_file_id"
            raise ValueError(msg)

        logger.debug(
            "batch_downloading_results",
            batch_id=batch.id,
            output_file_id=batch.output_file_id,
        )

        # Download results file
        output_file = await self.client.files.content(batch.output_file_id)

        # Parse JSONL results
        results = {}
        error_count = 0

        for line in output_file.text.strip().split("\n"):
            if not line:
                continue

            try:
                result = json.loads(line)

                # Check for errors in individual requests
                if "error" in result:
                    error_count += 1
                    logger.warning(
                        "batch_result_error",
                        custom_id=result.get("custom_id"),
                        error=result["error"],
                    )
                    continue

                custom_id = result["custom_id"]
                embedding = result["response"]["body"]["data"][0]["embedding"]

                # Validate dimensions
                if len(embedding) != self.dimensions:
                    logger.warning(
                        "batch_result_invalid_dimensions",
                        custom_id=custom_id,
                        expected=self.dimensions,
                        got=len(embedding),
                    )
                    continue

                # Apply L2 normalization
                results[custom_id] = normalize_vector(embedding)

            except (json.JSONDecodeError, KeyError, IndexError) as e:
                error_count += 1
                logger.warning(
                    "batch_result_parse_error",
                    line=line[:100],
                    error=str(e),
                )
                continue

        logger.info(
            "batch_results_downloaded",
            batch_id=batch.id,
            success_count=len(results),
            error_count=error_count,
        )

        return results


@lru_cache
def get_embedding_service() -> EmbeddingService:
    """Get cached embedding service instance."""
    return EmbeddingService()


__all__ = ["EmbeddingService", "EmbeddingVector", "get_embedding_service", "normalize_vector"]
