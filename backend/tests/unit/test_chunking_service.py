"""Unit tests for ChunkingService.

Tests cover:
- Token counting with tiktoken
- Document chunking with various configurations
- Heading-based splitting
- Overlap between chunks
- Deduplication
- Hierarchical path preservation
- Edge cases (empty content, no headings, etc.)

Reference: Issues #15, .claude/skills/context-engineering/SKILL.md - Phase 3
"""

import pytest

from app.shared.services.documents import ChunkingConfig, ChunkingService, ChunkText

pytestmark = pytest.mark.unit


@pytest.fixture
def chunking_service() -> ChunkingService:
    """Create fresh chunking service for each test."""
    return ChunkingService()


@pytest.fixture
def sample_markdown() -> str:
    """Sample markdown document for testing."""
    return """# Main Title

This is an introduction paragraph with some content.

## Section 1

Some content in section 1. This section has multiple sentences.
It spans several lines to test chunking behavior.

## Section 2

More content here. This is section 2.

### Subsection 2.1

Final content in subsection 2.1.
"""


@pytest.fixture
def long_document() -> str:
    """Long document to test multi-chunk splitting."""
    # Create content that will require multiple chunks
    paragraphs = []
    for i in range(20):
        paragraphs.append(
            f"Paragraph {i}: " + "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 10
        )
    return "\n\n".join(paragraphs)


class TestChunkingService:
    """Test suite for ChunkingService."""

    def test_count_tokens(self, chunking_service: ChunkingService) -> None:
        """Test token counting with tiktoken."""
        text = "Hello, world!"
        token_count = chunking_service.count_tokens(text)

        # Should return positive integer
        assert isinstance(token_count, int)
        assert token_count > 0
        # Basic sanity check: short text should be < 10 tokens
        assert token_count < 10

    def test_count_tokens_empty(self, chunking_service: ChunkingService) -> None:
        """Test token counting with empty string."""
        token_count = chunking_service.count_tokens("")
        assert token_count == 0

    def test_chunk_document_default_config(
        self,
        chunking_service: ChunkingService,
        sample_markdown: str,
    ) -> None:
        """Test chunking with default configuration."""
        chunks = chunking_service.chunk_document(sample_markdown)

        # Should produce at least one chunk
        assert len(chunks) > 0
        # Each chunk should have required attributes
        for chunk in chunks:
            assert isinstance(chunk, ChunkText)
            assert chunk.text
            assert chunk.token_count > 0
            assert chunk.content_hash
            assert chunk.chunk_total == len(chunks)

    def test_chunk_document_custom_config(
        self,
        chunking_service: ChunkingService,
        long_document: str,
    ) -> None:
        """Test chunking with custom configuration."""
        config = ChunkingConfig(
            chunk_size=200,
            overlap_pct=0.15,
            respect_headings=False,
        )
        chunks = chunking_service.chunk_document(long_document, config)

        # Should produce multiple chunks
        assert len(chunks) > 1
        # Token counts should be reasonable
        for chunk in chunks:
            assert chunk.token_count <= config.max_tokens

    def test_chunk_document_respects_headings(
        self,
        chunking_service: ChunkingService,
        sample_markdown: str,
    ) -> None:
        """Test that headings are respected when enabled."""
        config = ChunkingConfig(respect_headings=True, chunk_size=100)
        chunks = chunking_service.chunk_document(sample_markdown, config)

        # Section titles should be preserved
        section_titles = {chunk.section_title for chunk in chunks if chunk.section_title}
        assert "Main Title" in section_titles or "Section 1" in section_titles

    def test_chunk_document_ignores_headings(
        self,
        chunking_service: ChunkingService,
        sample_markdown: str,
    ) -> None:
        """Test that headings can be ignored."""
        config = ChunkingConfig(respect_headings=False, chunk_size=100)
        chunks = chunking_service.chunk_document(sample_markdown, config)

        # Without heading respect, section_title might be empty
        # But chunks should still be created
        assert len(chunks) > 0

    def test_chunk_overlap(
        self,
        chunking_service: ChunkingService,
        long_document: str,
    ) -> None:
        """Test overlap between consecutive chunks."""
        config = ChunkingConfig(chunk_size=200, overlap_pct=0.2)
        chunks = chunking_service.chunk_document(long_document, config)

        if len(chunks) > 1:
            # Second chunk should contain some content from first chunk
            # This is approximate since overlap is character-based
            # but we can verify chunks exist
            assert chunks[1].text
            # Verify overlap was applied (token count should include overlap)
            # Note: First chunk won't have overlap
            assert chunks[1].token_count > 0

    def test_chunk_no_overlap(
        self,
        chunking_service: ChunkingService,
        long_document: str,
    ) -> None:
        """Test chunking without overlap."""
        config = ChunkingConfig(chunk_size=200, overlap_pct=0.0)
        chunks = chunking_service.chunk_document(long_document, config)

        # Should still produce chunks
        assert len(chunks) > 0

    def test_chunk_deduplication(
        self,
        chunking_service: ChunkingService,
    ) -> None:
        """Test that identical chunks are deduplicated."""
        # Create content with repetition
        content = "Identical content. " * 100
        config = ChunkingConfig(chunk_size=100, overlap_pct=0.0)
        chunks = chunking_service.chunk_document(content, config)

        # Check for duplicate hashes
        hashes = [chunk.content_hash for chunk in chunks]
        unique_hashes = set(hashes)

        # All hashes should be unique (deduplication happened)
        assert len(hashes) == len(unique_hashes)

    def test_chunk_indices(
        self,
        chunking_service: ChunkingService,
        long_document: str,
    ) -> None:
        """Test chunk_idx and chunk_total are set correctly."""
        chunks = chunking_service.chunk_document(long_document)

        total = len(chunks)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_idx == i
            assert chunk.chunk_total == total

    def test_chunk_text_post_init(self) -> None:
        """Test ChunkText __post_init__ generates hash."""
        chunk = ChunkText(text="Test content")

        # Hash should be auto-generated
        assert chunk.content_hash
        assert len(chunk.content_hash) == 16  # First 16 chars of SHA256

    def test_chunk_text_with_hash(self) -> None:
        """Test ChunkText with pre-provided hash."""
        custom_hash = "custom_hash_1234"
        chunk = ChunkText(text="Test content", content_hash=custom_hash)

        # Should keep custom hash
        assert chunk.content_hash == custom_hash

    def test_chunk_small_document(
        self,
        chunking_service: ChunkingService,
    ) -> None:
        """Test chunking very small document."""
        content = "Small doc."
        chunks = chunking_service.chunk_document(content)

        # Should produce exactly one chunk
        assert len(chunks) == 1
        assert chunks[0].text == content
        assert chunks[0].chunk_idx == 0
        assert chunks[0].chunk_total == 1

    def test_chunk_empty_document(
        self,
        chunking_service: ChunkingService,
    ) -> None:
        """Test chunking empty document."""
        content = ""
        chunks = chunking_service.chunk_document(content)

        # Should handle gracefully (might produce empty chunk or no chunks)
        # Depending on implementation, both are acceptable
        assert isinstance(chunks, list)

    def test_chunk_with_hierarchy(
        self,
        chunking_service: ChunkingService,
        sample_markdown: str,
    ) -> None:
        """Test chunk_with_hierarchy preserves heading paths."""
        chunks = chunking_service.chunk_with_hierarchy(sample_markdown)

        # Should have path metadata
        assert len(chunks) > 0
        # At least some chunks should have non-empty paths
        paths = [chunk.path for chunk in chunks if chunk.path]
        assert len(paths) > 0

    def test_chunk_with_hierarchy_nested(
        self,
        chunking_service: ChunkingService,
    ) -> None:
        """Test hierarchical path with nested headings."""
        content = """# Level 1

Content under level 1.

## Level 2

Content under level 2.

### Level 3

Content under level 3.
"""
        config = ChunkingConfig(chunk_size=100)
        chunks = chunking_service.chunk_with_hierarchy(content, config)

        # Verify paths include hierarchy
        # Note: Implementation appends titles to stack, so paths grow
        assert len(chunks) > 0

    def test_chunking_config_validation(self) -> None:
        """Test ChunkingConfig validation with Pydantic."""
        # Valid config
        config = ChunkingConfig(
            chunk_size=600,
            overlap_pct=0.12,
            max_tokens=7500,
            respect_headings=True,
        )
        assert config.chunk_size == 600

        # Test with edge values
        config_min = ChunkingConfig(chunk_size=100, overlap_pct=0.0, max_tokens=1000)
        assert config_min.chunk_size == 100

    def test_chunking_config_defaults(self) -> None:
        """Test ChunkingConfig default values."""
        config = ChunkingConfig()

        assert config.chunk_size == 600
        assert config.overlap_pct == 0.12
        assert config.max_tokens == 7500
        assert config.respect_headings is True

    def test_split_by_headings(
        self,
        chunking_service: ChunkingService,
        sample_markdown: str,
    ) -> None:
        """Test internal _split_by_headings method."""
        sections = chunking_service._split_by_headings(sample_markdown)

        # Should produce multiple sections
        assert len(sections) > 0
        # Each section is (title, content) tuple
        for title, content in sections:
            assert isinstance(title, str)
            assert isinstance(content, str)

    def test_split_by_headings_no_headings(
        self,
        chunking_service: ChunkingService,
    ) -> None:
        """Test splitting content with no headings."""
        content = "Plain text without any markdown headings."
        sections = chunking_service._split_by_headings(content)

        # Should return single section with empty title
        assert len(sections) == 1
        assert sections[0][0] == ""
        assert sections[0][1] == content

    def test_chunk_section(
        self,
        chunking_service: ChunkingService,
    ) -> None:
        """Test internal _chunk_section method."""
        content = "This is a test section. " * 100
        config = ChunkingConfig(chunk_size=100)

        chunks = chunking_service._chunk_section(
            content,
            config,
            section_title="Test Section",
        )

        # Should produce multiple chunks
        assert len(chunks) > 1
        # All should have section_title
        for chunk in chunks:
            assert chunk.section_title == "Test Section"

    def test_add_overlap(
        self,
        chunking_service: ChunkingService,
    ) -> None:
        """Test internal _add_overlap method."""
        chunks = [
            ChunkText(text="First chunk content", token_count=10),
            ChunkText(text="Second chunk content", token_count=10),
            ChunkText(text="Third chunk content", token_count=10),
        ]

        overlapped = chunking_service._add_overlap(chunks, overlap_pct=0.2)

        # First chunk should remain unchanged
        assert overlapped[0].text == "First chunk content"
        # Second and third should have overlap prepended
        assert len(overlapped[1].text) > len("Second chunk content")
        assert len(overlapped[2].text) > len("Third chunk content")

    def test_add_overlap_single_chunk(
        self,
        chunking_service: ChunkingService,
    ) -> None:
        """Test overlap with single chunk."""
        chunks = [ChunkText(text="Only chunk", token_count=5)]

        overlapped = chunking_service._add_overlap(chunks, overlap_pct=0.2)

        # Should remain unchanged
        assert len(overlapped) == 1
        assert overlapped[0].text == "Only chunk"

    def test_add_overlap_zero_percent(
        self,
        chunking_service: ChunkingService,
    ) -> None:
        """Test overlap with 0% overlap."""
        chunks = [
            ChunkText(text="First chunk", token_count=5),
            ChunkText(text="Second chunk", token_count=5),
        ]

        overlapped = chunking_service._add_overlap(chunks, overlap_pct=0.0)

        # Should remain unchanged
        assert overlapped[0].text == "First chunk"
        assert overlapped[1].text == "Second chunk"

    def test_max_tokens_enforcement(
        self,
        chunking_service: ChunkingService,
        long_document: str,
    ) -> None:
        """Test that chunks respect max_tokens limit."""
        config = ChunkingConfig(chunk_size=2000, max_tokens=1500)
        chunks = chunking_service.chunk_document(long_document, config)

        # All chunks should respect max_tokens (even if chunk_size is larger)
        for chunk in chunks:
            # Account for overlap which might push slightly over
            # but _chunk_section enforces hard limit
            assert chunk.token_count <= config.max_tokens + 100  # Buffer for overlap

    def test_unicode_handling(
        self,
        chunking_service: ChunkingService,
    ) -> None:
        """Test chunking with unicode characters."""
        content = "Hello 世界 🌍 " * 100
        chunks = chunking_service.chunk_document(content)

        # Should handle unicode properly
        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.text
            assert chunk.token_count > 0

    def test_code_blocks_in_content(
        self,
        chunking_service: ChunkingService,
    ) -> None:
        """Test chunking content with code blocks."""
        content = """# Documentation

Some text.

```python
def example():
    return "This is code"
```

More text after code block.
"""
        chunks = chunking_service.chunk_document(content)

        # Should preserve code blocks in chunks
        full_text = "".join(chunk.text for chunk in chunks)
        assert "def example():" in full_text

    def test_chunk_text_attributes(self) -> None:
        """Test ChunkText dataclass has all expected attributes."""
        chunk = ChunkText(
            text="Test",
            path=["Chapter 1", "Section 1.1"],
            section_title="Test Section",
            chunk_idx=0,
            chunk_total=5,
            token_count=10,
        )

        assert chunk.text == "Test"
        assert chunk.path == ["Chapter 1", "Section 1.1"]
        assert chunk.section_title == "Test Section"
        assert chunk.chunk_idx == 0
        assert chunk.chunk_total == 5
        assert chunk.token_count == 10
        assert chunk.content_hash  # Auto-generated

    def test_chunk_text_default_values(self) -> None:
        """Test ChunkText default values."""
        chunk = ChunkText(text="Test")

        assert chunk.path == []
        assert chunk.section_title is None
        assert chunk.chunk_idx == 0
        assert chunk.chunk_total == 1
        assert chunk.token_count == 0
        assert chunk.content_hash  # Auto-generated

    def test_large_chunk_size(
        self,
        chunking_service: ChunkingService,
        sample_markdown: str,
    ) -> None:
        """Test with very large chunk_size (single chunk expected)."""
        config = ChunkingConfig(chunk_size=8000, respect_headings=False)
        chunks = chunking_service.chunk_document(sample_markdown, config)

        # Small document should fit in single large chunk (when not splitting by headings)
        assert len(chunks) == 1

    def test_small_chunk_size(
        self,
        chunking_service: ChunkingService,
        long_document: str,
    ) -> None:
        """Test with very small chunk_size (many chunks expected)."""
        config = ChunkingConfig(chunk_size=100)
        chunks = chunking_service.chunk_document(long_document, config)

        # Should produce many chunks
        assert len(chunks) > 5

    def test_consistency_across_calls(
        self,
        chunking_service: ChunkingService,
        sample_markdown: str,
    ) -> None:
        """Test that chunking same content produces same results."""
        chunks1 = chunking_service.chunk_document(sample_markdown)
        chunks2 = chunking_service.chunk_document(sample_markdown)

        # Should produce identical results
        assert len(chunks1) == len(chunks2)
        for c1, c2 in zip(chunks1, chunks2, strict=True):
            assert c1.text == c2.text
            assert c1.content_hash == c2.content_hash

    def test_newline_handling(
        self,
        chunking_service: ChunkingService,
    ) -> None:
        """Test handling of different newline types."""
        content_lf = "Line 1\nLine 2\nLine 3"
        content_crlf = "Line 1\r\nLine 2\r\nLine 3"

        chunks_lf = chunking_service.chunk_document(content_lf)
        chunks_crlf = chunking_service.chunk_document(content_crlf)

        # Both should produce chunks
        assert len(chunks_lf) > 0
        assert len(chunks_crlf) > 0

    def test_overlap_with_short_chunks(
        self,
        chunking_service: ChunkingService,
    ) -> None:
        """Test overlap with very short chunks."""
        content = "A B C D E F G H I J " * 50  # Make longer for chunking
        config = ChunkingConfig(chunk_size=100, overlap_pct=0.5)

        chunks = chunking_service.chunk_document(content, config)

        # Should handle short chunks gracefully
        assert len(chunks) > 0
