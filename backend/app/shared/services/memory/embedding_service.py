"""Embedding generation service using OpenAI text-embedding-3-small."""

import math
from functools import lru_cache

import tiktoken
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

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

    async def generate_embedding(self, text: str) -> EmbeddingVector:
        """Generate a 1536-dimensional L2-normalized embedding vector.

        Args:
            text: The input text to embed. Truncated to MAX_TOKENS (8000) tokens.

        Returns:
            A list of 1536 L2-normalized floats representing the semantic embedding.

        Raises:
            ValueError: If text is empty.
            OpenAIError: If the API call fails.
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

    async def generate_embeddings_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[EmbeddingVector]:
        """Generate L2-normalized embeddings for multiple texts.

        Processes texts in batches for efficiency.

        Args:
            texts: List of texts to embed.
            batch_size: Number of texts per API call (max 2048).

        Returns:
            List of L2-normalized embedding vectors in the same order as input.
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


@lru_cache
def get_embedding_service() -> EmbeddingService:
    """Get cached embedding service instance."""
    return EmbeddingService()


__all__ = ["EmbeddingService", "EmbeddingVector", "get_embedding_service", "normalize_vector"]
