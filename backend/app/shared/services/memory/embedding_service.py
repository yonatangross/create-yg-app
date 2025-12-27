"""Embedding generation service using OpenAI text-embedding-3-small."""

from functools import lru_cache

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Type alias for embedding vectors
EmbeddingVector = list[float]


class EmbeddingService:
    """Generate embeddings via OpenAI text-embedding-3-small.

    Produces 1536-dimensional vectors optimized for semantic similarity search.

    Attributes:
        model: The OpenAI embedding model to use.
        dimensions: The output vector dimensions (1536).

    Example:
        service = EmbeddingService()
        embedding = await service.generate_embedding("Hello, world!")
        # embedding is a list of 1536 floats
    """

    def __init__(self) -> None:
        """Initialize the embedding service."""
        if not settings.OPENAI_API_KEY:
            msg = "OPENAI_API_KEY is required for embeddings"
            raise ValueError(msg)

        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "text-embedding-3-small"
        self.dimensions = 1536
        self._max_input_tokens = 8191  # Model limit

    async def generate_embedding(self, text: str) -> EmbeddingVector:
        """Generate a 1536-dimensional embedding vector.

        Args:
            text: The input text to embed. Truncated to ~8000 tokens.

        Returns:
            A list of 1536 floats representing the semantic embedding.

        Raises:
            ValueError: If text is empty.
            OpenAIError: If the API call fails.
        """
        if not text or not text.strip():
            msg = "Cannot generate embedding for empty text"
            raise ValueError(msg)

        # Truncate to avoid token limit (rough estimate: 4 chars = 1 token)
        max_chars = self._max_input_tokens * 4
        truncated = text[:max_chars] if len(text) > max_chars else text

        logger.debug(
            "generating_embedding",
            text_length=len(text),
            truncated=len(text) > max_chars,
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

        logger.debug(
            "embedding_generated",
            dimensions=len(embedding),
            usage_tokens=response.usage.total_tokens,
        )

        return embedding

    async def generate_embeddings_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[EmbeddingVector]:
        """Generate embeddings for multiple texts.

        Processes texts in batches for efficiency.

        Args:
            texts: List of texts to embed.
            batch_size: Number of texts per API call (max 2048).

        Returns:
            List of embedding vectors in the same order as input.
        """
        if not texts:
            return []

        all_embeddings: list[EmbeddingVector] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            # Truncate each text
            max_chars = self._max_input_tokens * 4
            truncated_batch = [t[:max_chars] if len(t) > max_chars else t for t in batch]

            response = await self.client.embeddings.create(
                model=self.model,
                input=truncated_batch,
            )

            # Extract embeddings in order
            batch_embeddings = [d.embedding for d in response.data]
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
