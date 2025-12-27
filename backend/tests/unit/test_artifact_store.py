"""Unit tests for ArtifactStore.

Tests cover:
- Content storage and URI generation
- Section extraction (summaries, code blocks, headings)
- Selective loading by section type
- Metadata retrieval
- Deletion
- Error handling

Reference: Issues #14, .claude/skills/context-engineering/SKILL.md - Phase 3
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.shared.services.documents import Artifact, ArtifactSection, ArtifactStore


@pytest.fixture
def artifact_store() -> ArtifactStore:
    """Create fresh artifact store for each test."""
    return ArtifactStore()


@pytest.fixture
def sample_markdown() -> str:
    """Sample markdown document for testing."""
    return """# Main Title

This is an introduction paragraph.

## Section 1

Some content in section 1.

```python
def hello():
    print("Hello, world!")
```

## Section 2

More content here.

```typescript
function greet(name: string): void {
    console.log(`Hello, ${name}`);
}
```

### Subsection 2.1

Final content.
"""


@pytest.fixture
def large_content() -> str:
    """Large content (>5KB) to trigger summarization."""
    # Generate ~6KB of content
    return "Lorem ipsum dolor sit amet. " * 250


class TestArtifactStore:
    """Test suite for ArtifactStore."""

    @pytest.mark.asyncio
    async def test_store_creates_valid_uri(
        self,
        artifact_store: ArtifactStore,
    ) -> None:
        """Test that storing content returns valid URI."""
        content = "Test content"
        uri = await artifact_store.store(content)

        assert uri.startswith("artifact://")
        assert len(uri.split("://")[1]) == 16  # Hash length

    @pytest.mark.asyncio
    async def test_store_with_custom_id(
        self,
        artifact_store: ArtifactStore,
    ) -> None:
        """Test custom artifact ID."""
        content = "Test content"
        uri = await artifact_store.store(content, artifact_id="custom-id")

        assert uri == "artifact://custom-id"

    @pytest.mark.asyncio
    async def test_load_full_content(
        self,
        artifact_store: ArtifactStore,
    ) -> None:
        """Test loading full content."""
        content = "Full test content"
        uri = await artifact_store.store(content)

        loaded = await artifact_store.load(uri, ArtifactSection.FULL)

        assert loaded == content

    @pytest.mark.asyncio
    async def test_load_summary_small_content(
        self,
        artifact_store: ArtifactStore,
    ) -> None:
        """Test summary for content below threshold (no summarization)."""
        content = "Small content"
        uri = await artifact_store.store(content)

        summary = await artifact_store.load(uri, ArtifactSection.SUMMARY)

        # Small content: summary should be full content truncated to max chars
        assert summary == content

    @pytest.mark.asyncio
    async def test_load_summary_large_content(
        self,
        artifact_store: ArtifactStore,
        large_content: str,
    ) -> None:
        """Test summary generation for large content."""
        uri = await artifact_store.store(large_content)

        summary = await artifact_store.load(uri, ArtifactSection.SUMMARY)

        # Should be summarized
        assert len(summary) <= artifact_store.SUMMARY_MAX_CHARS + 3  # +3 for "..."
        assert summary.endswith("...") or len(summary) <= artifact_store.SUMMARY_MAX_CHARS

    @pytest.mark.asyncio
    async def test_load_first_n_chars(
        self,
        artifact_store: ArtifactStore,
        large_content: str,
    ) -> None:
        """Test loading first N characters."""
        uri = await artifact_store.store(large_content)

        preview = await artifact_store.load(uri, ArtifactSection.FIRST_N)

        assert len(preview) == min(
            len(large_content),
            artifact_store.DEFAULT_FIRST_N_CHARS,
        )

    @pytest.mark.asyncio
    async def test_extract_code_blocks(
        self,
        artifact_store: ArtifactStore,
        sample_markdown: str,
    ) -> None:
        """Test code block extraction."""
        uri = await artifact_store.store(sample_markdown)

        code_blocks = await artifact_store.load(uri, ArtifactSection.CODE_BLOCKS)

        # Should contain both Python and TypeScript blocks
        assert "def hello():" in code_blocks
        assert "function greet" in code_blocks
        # Should NOT contain fence markers
        assert "```python" not in code_blocks

    @pytest.mark.asyncio
    async def test_extract_headings(
        self,
        artifact_store: ArtifactStore,
        sample_markdown: str,
    ) -> None:
        """Test heading extraction."""
        uri = await artifact_store.store(sample_markdown)

        headings = await artifact_store.load(uri, ArtifactSection.HEADINGS)

        # Should contain all headings without # markers
        assert "Main Title" in headings
        assert "Section 1" in headings
        assert "Section 2" in headings
        assert "Subsection 2.1" in headings
        assert "#" not in headings  # No markers

    @pytest.mark.asyncio
    async def test_get_metadata(
        self,
        artifact_store: ArtifactStore,
        sample_markdown: str,
    ) -> None:
        """Test metadata retrieval."""
        uri = await artifact_store.store(sample_markdown)

        metadata = await artifact_store.get_metadata(uri)

        assert "size_bytes" in metadata
        assert metadata["size_bytes"] == len(sample_markdown.encode())
        assert "content_hash" in metadata
        assert len(metadata["content_hash"]) == 16
        assert "code_blocks_count" in metadata
        assert metadata["code_blocks_count"] == 2  # Python + TypeScript
        assert "headings_count" in metadata
        assert metadata["headings_count"] == 4

    @pytest.mark.asyncio
    async def test_delete_artifact(
        self,
        artifact_store: ArtifactStore,
    ) -> None:
        """Test artifact deletion."""
        content = "To be deleted"
        uri = await artifact_store.store(content)

        # Delete should succeed
        result = await artifact_store.delete(uri)
        assert result is True

        # Should not be able to load after deletion
        with pytest.raises(ValueError, match="Artifact not found"):
            await artifact_store.load(uri)

    @pytest.mark.asyncio
    async def test_delete_nonexistent(
        self,
        artifact_store: ArtifactStore,
    ) -> None:
        """Test deleting non-existent artifact."""
        result = await artifact_store.delete("artifact://nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_load_nonexistent_artifact(
        self,
        artifact_store: ArtifactStore,
    ) -> None:
        """Test loading non-existent artifact raises error."""
        with pytest.raises(ValueError, match="Artifact not found"):
            await artifact_store.load("artifact://nonexistent")

    @pytest.mark.asyncio
    async def test_get_metadata_nonexistent(
        self,
        artifact_store: ArtifactStore,
    ) -> None:
        """Test metadata for non-existent artifact raises error."""
        with pytest.raises(ValueError, match="Artifact not found"):
            await artifact_store.get_metadata("artifact://nonexistent")

    @pytest.mark.asyncio
    async def test_content_hash_consistency(
        self,
        artifact_store: ArtifactStore,
    ) -> None:
        """Test same content produces same hash."""
        content = "Identical content"

        uri1 = await artifact_store.store(content)
        uri2 = await artifact_store.store(content)

        # URIs should be identical (same hash)
        assert uri1 == uri2

    @pytest.mark.asyncio
    async def test_no_code_blocks(
        self,
        artifact_store: ArtifactStore,
    ) -> None:
        """Test document with no code blocks."""
        content = "Just plain text without code blocks."
        uri = await artifact_store.store(content)

        code_blocks = await artifact_store.load(uri, ArtifactSection.CODE_BLOCKS)

        assert code_blocks == ""  # Empty string when joined

    @pytest.mark.asyncio
    async def test_no_headings(
        self,
        artifact_store: ArtifactStore,
    ) -> None:
        """Test document with no headings."""
        content = "Just plain text without headings."
        uri = await artifact_store.store(content)

        headings = await artifact_store.load(uri, ArtifactSection.HEADINGS)

        assert headings == ""  # Empty string when joined

    @pytest.mark.asyncio
    async def test_artifact_dataclass_attributes(
        self,
        artifact_store: ArtifactStore,
        sample_markdown: str,
    ) -> None:
        """Test Artifact dataclass has all expected attributes."""
        uri = await artifact_store.store(sample_markdown)

        # Access artifact via backend to test structure
        artifact = await artifact_store.backend.get(uri)

        assert isinstance(artifact, Artifact)
        assert artifact.uri == uri
        assert artifact.full_content == sample_markdown
        assert isinstance(artifact.code_blocks, list)
        assert isinstance(artifact.headings, list)
        assert isinstance(artifact.size_bytes, int)
        assert isinstance(artifact.content_hash, str)
        assert artifact.summary is None or isinstance(artifact.summary, str)

    @pytest.mark.asyncio
    async def test_summary_threshold(
        self,
        artifact_store: ArtifactStore,
    ) -> None:
        """Test that summary is only generated above threshold."""
        # Content just below threshold
        small_content = "x" * (artifact_store.SUMMARY_THRESHOLD_BYTES - 100)
        uri_small = await artifact_store.store(small_content)
        artifact_small = await artifact_store.backend.get(uri_small)

        assert artifact_small.summary is None

        # Content just above threshold
        large_content = "x" * (artifact_store.SUMMARY_THRESHOLD_BYTES + 100)
        uri_large = await artifact_store.store(large_content)
        artifact_large = await artifact_store.backend.get(uri_large)

        assert artifact_large.summary is not None

    @pytest.mark.asyncio
    async def test_multiple_artifacts_isolation(
        self,
        artifact_store: ArtifactStore,
    ) -> None:
        """Test that multiple artifacts don't interfere."""
        content1 = "First artifact"
        content2 = "Second artifact"

        uri1 = await artifact_store.store(content1, artifact_id="first")
        uri2 = await artifact_store.store(content2, artifact_id="second")

        loaded1 = await artifact_store.load(uri1, ArtifactSection.FULL)
        loaded2 = await artifact_store.load(uri2, ArtifactSection.FULL)

        assert loaded1 == content1
        assert loaded2 == content2

    @pytest.mark.asyncio
    async def test_unicode_content(
        self,
        artifact_store: ArtifactStore,
    ) -> None:
        """Test handling of unicode content."""
        content = "Hello 世界 🌍 Привет"
        uri = await artifact_store.store(content)

        loaded = await artifact_store.load(uri, ArtifactSection.FULL)

        assert loaded == content

    @pytest.mark.asyncio
    async def test_empty_content(
        self,
        artifact_store: ArtifactStore,
    ) -> None:
        """Test handling of empty content."""
        content = ""
        uri = await artifact_store.store(content)

        loaded = await artifact_store.load(uri, ArtifactSection.FULL)

        assert loaded == ""
        metadata = await artifact_store.get_metadata(uri)
        assert metadata["size_bytes"] == 0

    @pytest.mark.asyncio
    async def test_default_section_is_summary(
        self,
        artifact_store: ArtifactStore,
    ) -> None:
        """Test that default section when loading is SUMMARY."""
        content = "Test content"
        uri = await artifact_store.store(content)

        # Load without specifying section
        default_load = await artifact_store.load(uri)
        summary_load = await artifact_store.load(uri, ArtifactSection.SUMMARY)

        assert default_load == summary_load


class TestRedisBackend:
    """Tests for RedisBackend artifact storage."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = MagicMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        redis.delete = AsyncMock(return_value=1)
        return redis

    @pytest.fixture
    def redis_backend(self, mock_redis):
        """Create RedisBackend with mocked Redis."""
        from app.shared.services.documents.artifact_store import RedisBackend

        return RedisBackend(mock_redis, ttl=3600)

    @pytest.mark.asyncio
    async def test_redis_backend_get_miss(self, redis_backend, mock_redis):
        """Test Redis backend cache miss."""
        mock_redis.get = AsyncMock(return_value=None)
        result = await redis_backend.get("artifact://test")

        assert result is None
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_backend_get_hit(self, redis_backend, mock_redis):
        """Test Redis backend cache hit."""
        import json

        artifact_data = {
            "uri": "artifact://test",
            "full_content": "Test content",
            "summary": None,
            "code_blocks": [],
            "headings": [],
            "size_bytes": 12,
            "content_hash": "abc123",
        }

        mock_redis.get = AsyncMock(return_value=json.dumps(artifact_data))
        result = await redis_backend.get("artifact://test")

        assert result is not None
        assert isinstance(result, Artifact)
        assert result.full_content == "Test content"
        assert result.uri == "artifact://test"

    @pytest.mark.asyncio
    async def test_redis_backend_set(self, redis_backend, mock_redis):
        """Test Redis backend stores artifact."""
        artifact = Artifact(
            uri="artifact://test",
            full_content="Test content",
            summary=None,
            code_blocks=[],
            headings=[],
            size_bytes=12,
            content_hash="abc123",
        )

        await redis_backend.set("artifact://test", artifact)

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 3600  # TTL

    @pytest.mark.asyncio
    async def test_redis_backend_delete_success(self, redis_backend):
        """Test Redis backend deletes artifact."""
        redis_backend.redis.delete = AsyncMock(return_value=1)  # 1 key deleted

        result = await redis_backend.delete("artifact://test")

        assert result is True
        redis_backend.redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_backend_delete_not_found(self, redis_backend):
        """Test Redis backend delete on non-existent key."""
        redis_backend.redis.delete = AsyncMock(return_value=0)  # 0 keys deleted

        result = await redis_backend.delete("artifact://nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_redis_backend_handles_errors_gracefully(self, redis_backend):
        """Test Redis backend handles errors without raising."""
        redis_backend.redis.get = AsyncMock(side_effect=Exception("Redis error"))

        # Should return None on error, not raise
        result = await redis_backend.get("artifact://test")
        assert result is None

    def test_redis_key_generation(self, redis_backend):
        """Test Redis key format."""
        key = redis_backend._redis_key("artifact://test123")

        assert key == "artifact:artifact://test123"
        assert key.startswith("artifact:")


class TestArtifactStoreWithDifferentBackends:
    """Test ArtifactStore with different backend implementations."""

    @pytest.mark.asyncio
    async def test_store_with_in_memory_backend(self):
        """Test ArtifactStore with default InMemoryBackend."""
        from app.shared.services.documents import ArtifactSection

        store = ArtifactStore()  # Uses InMemoryBackend by default
        uri = await store.store("Test content")

        assert uri.startswith("artifact://")

        # Should be able to load back
        content = await store.load(uri, ArtifactSection.FULL)
        assert content == "Test content"

    @pytest.mark.asyncio
    async def test_store_with_explicit_backend(self):
        """Test ArtifactStore with explicitly provided backend."""
        from app.shared.services.documents import ArtifactSection
        from app.shared.services.documents.artifact_store import InMemoryBackend

        backend = InMemoryBackend()
        store = ArtifactStore(backend=backend)

        uri = await store.store("Test with explicit backend")
        content = await store.load(uri, ArtifactSection.FULL)

        assert content == "Test with explicit backend"
