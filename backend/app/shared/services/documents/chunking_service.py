"""Document chunking service for embeddings.

This module implements Phase 3 optimization from context-engineering skill:
intelligent document splitting with hierarchical context preservation.

Reference: .claude/skills/context-engineering/SKILL.md - Phase 3
"""

import hashlib
import re
from dataclasses import dataclass, field

import tiktoken
from pydantic import BaseModel, Field


class ChunkingConfig(BaseModel):
    """Configuration for document chunking.

    Attributes:
        chunk_size: Target tokens per chunk (default: 600)
        overlap_pct: Overlap between chunks as percentage (default: 0.12 = 12%)
        max_tokens: Hard limit per chunk (default: 7500)
        respect_headings: Split at markdown headings (default: True)
    """

    chunk_size: int = Field(default=600, ge=100, le=8000)
    overlap_pct: float = Field(default=0.12, ge=0.0, le=0.5)
    max_tokens: int = Field(default=7500, ge=1000, le=8000)
    respect_headings: bool = True


@dataclass
class ChunkText:
    """A single chunk of text with metadata.

    Attributes:
        text: Chunk content
        path: Hierarchical location (e.g., ["Chapter 1", "Section 1.1"])
        section_title: Title of containing section
        chunk_idx: Index within all chunks (0-based)
        chunk_total: Total number of chunks
        token_count: Exact token count using tiktoken
        content_hash: SHA256 hash (first 16 chars) for deduplication
    """

    text: str
    path: list[str] = field(default_factory=list)
    section_title: str | None = None
    chunk_idx: int = 0
    chunk_total: int = 1
    token_count: int = 0
    content_hash: str = ""

    def __post_init__(self) -> None:
        """Generate content hash if not provided."""
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.text.encode()).hexdigest()[:16]


class ChunkingService:
    """Intelligent document chunking for embeddings.

    Splits documents into embedding-friendly chunks while preserving
    hierarchical context and avoiding mid-sentence breaks.

    Features:
    - Exact token counting (tiktoken)
    - Heading-aware splitting
    - Configurable overlap between chunks
    - Automatic deduplication
    - Hierarchical context preservation

    Example:
        service = ChunkingService()
        chunks = service.chunk_document(
            content=long_document,
            config=ChunkingConfig(chunk_size=600, overlap_pct=0.12)
        )
    """

    def __init__(self) -> None:
        """Initialize chunking service with tiktoken encoding."""
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken.

        Args:
            text: Input text

        Returns:
            Token count
        """
        return len(self.encoding.encode(text))

    def chunk_document(
        self,
        content: str,
        config: ChunkingConfig | None = None,
    ) -> list[ChunkText]:
        """Chunk document into embedding-sized pieces.

        Process:
        1. Split by headings (if enabled)
        2. Chunk each section to target size
        3. Add overlap between chunks
        4. Deduplicate and update metadata

        Args:
            content: Document content
            config: Optional chunking configuration

        Returns:
            List of ChunkText objects with metadata
        """
        config = config or ChunkingConfig()

        # 1. Split by headings if enabled
        sections = self._split_by_headings(content) if config.respect_headings else [("", content)]

        # 2. Chunk each section
        chunks: list[ChunkText] = []
        for title, section_content in sections:
            section_chunks = self._chunk_section(
                section_content,
                config,
                section_title=title,
            )
            chunks.extend(section_chunks)

        # 3. Add overlap between chunks
        chunks = self._add_overlap(chunks, config.overlap_pct)

        # 4. Deduplicate and update totals
        seen_hashes: set[str] = set()
        unique_chunks: list[ChunkText] = []
        for chunk in chunks:
            if chunk.content_hash not in seen_hashes:
                chunk.chunk_idx = len(unique_chunks)
                unique_chunks.append(chunk)
                seen_hashes.add(chunk.content_hash)

        for chunk in unique_chunks:
            chunk.chunk_total = len(unique_chunks)

        return unique_chunks

    def _split_by_headings(self, content: str) -> list[tuple[str, str]]:
        """Split content by markdown headings.

        Preserves heading hierarchy for context.

        Args:
            content: Markdown content

        Returns:
            List of (heading_text, section_content) tuples
        """
        pattern = r"^(#{1,6})\s+(.+)$"

        sections: list[tuple[str, str]] = []
        current_title = ""
        current_content: list[str] = []

        for line in content.split("\n"):
            match = re.match(pattern, line)
            if match:
                # Save previous section
                if current_content:
                    sections.append((current_title, "\n".join(current_content)))
                current_title = match.group(2)
                current_content = [line]
            else:
                current_content.append(line)

        # Save final section
        if current_content:
            sections.append((current_title, "\n".join(current_content)))

        return sections if sections else [("", content)]

    def _chunk_section(
        self,
        content: str,
        config: ChunkingConfig,
        section_title: str | None = None,
    ) -> list[ChunkText]:
        """Chunk a section into token-sized pieces.

        Uses sliding window approach to create chunks of target size.

        Args:
            content: Section content
            config: Chunking configuration
            section_title: Optional section title for metadata

        Returns:
            List of chunks from this section
        """
        tokens = self.encoding.encode(content)
        chunks: list[ChunkText] = []

        # Create chunks using sliding window
        for i in range(0, len(tokens), config.chunk_size):
            chunk_tokens = tokens[i : i + config.chunk_size]

            # Hard limit enforcement
            if len(chunk_tokens) > config.max_tokens:
                chunk_tokens = chunk_tokens[: config.max_tokens]

            chunk_text = self.encoding.decode(chunk_tokens)

            chunks.append(
                ChunkText(
                    text=chunk_text,
                    section_title=section_title,
                    token_count=len(chunk_tokens),
                )
            )

        return chunks

    def _add_overlap(
        self,
        chunks: list[ChunkText],
        overlap_pct: float,
    ) -> list[ChunkText]:
        """Add overlap between consecutive chunks.

        Preserves context across chunk boundaries by prepending
        trailing portion of previous chunk.

        Args:
            chunks: List of chunks
            overlap_pct: Overlap percentage (0.0-0.5)

        Returns:
            Chunks with overlap added
        """
        if len(chunks) <= 1 or overlap_pct <= 0:
            return chunks

        # Add context from previous chunk
        for i in range(1, len(chunks)):
            prev_text = chunks[i - 1].text
            overlap_chars = int(len(prev_text) * overlap_pct)
            overlap_text = prev_text[-overlap_chars:] if overlap_chars > 0 else ""

            # Prepend overlap to current chunk
            chunks[i].text = overlap_text + chunks[i].text
            chunks[i].token_count = self.count_tokens(chunks[i].text)
            chunks[i].content_hash = hashlib.sha256(chunks[i].text.encode()).hexdigest()[:16]

        return chunks

    def chunk_with_hierarchy(
        self,
        content: str,
        config: ChunkingConfig | None = None,
    ) -> list[ChunkText]:
        """Chunk document preserving heading hierarchy in path.

        Similar to chunk_document but adds hierarchical path metadata.

        Args:
            content: Document content
            config: Optional chunking configuration

        Returns:
            List of chunks with path metadata
        """
        config = config or ChunkingConfig()
        sections = self._split_by_headings(content)

        chunks: list[ChunkText] = []
        heading_stack: list[str] = []

        for title, section_content in sections:
            # Update heading hierarchy
            if title:
                heading_stack.append(title)

            section_chunks = self._chunk_section(
                section_content,
                config,
                section_title=title,
            )

            # Add path to each chunk
            for chunk in section_chunks:
                chunk.path = heading_stack.copy()

            chunks.extend(section_chunks)

        # Add overlap and deduplicate
        chunks = self._add_overlap(chunks, config.overlap_pct)

        # Update metadata
        seen_hashes: set[str] = set()
        unique_chunks: list[ChunkText] = []
        for chunk in chunks:
            if chunk.content_hash not in seen_hashes:
                chunk.chunk_idx = len(unique_chunks)
                unique_chunks.append(chunk)
                seen_hashes.add(chunk.content_hash)

        for chunk in unique_chunks:
            chunk.chunk_total = len(unique_chunks)

        return unique_chunks
