"""Artifact storage for large content handling.

This module implements Phase 3 optimization from context-engineering skill:
storing large content externally and loading sections on-demand.

Reference: .claude/skills/context-engineering/SKILL.md - Phase 3
"""

import hashlib
import re
from dataclasses import dataclass
from enum import Enum


class ArtifactSection(str, Enum):
    """Section types for selective artifact loading.

    Attributes:
        SUMMARY: Compressed overview (max 2000 chars)
        FULL: Complete original content
        FIRST_N: First N characters (default 5000)
        CODE_BLOCKS: Extracted code blocks only
        HEADINGS: Document outline (markdown headings)
    """

    SUMMARY = "summary"
    FULL = "full"
    FIRST_N = "first_n"
    CODE_BLOCKS = "code_blocks"
    HEADINGS = "headings"


@dataclass
class Artifact:
    """Stored artifact with pre-extracted sections.

    Attributes:
        uri: Unique identifier (artifact://<id>)
        full_content: Complete original content
        summary: Optional compressed summary
        code_blocks: Extracted code blocks
        headings: Markdown heading hierarchy
        size_bytes: Content size in bytes
        content_hash: SHA256 hash (first 16 chars)
    """

    uri: str
    full_content: str
    summary: str | None
    code_blocks: list[str]
    headings: list[str]
    size_bytes: int
    content_hash: str


class ArtifactStore:
    """In-memory store for large content with selective loading.

    Stores content externally to context window and loads sections
    on-demand. Automatically generates summaries for content >5KB.

    Example:
        store = ArtifactStore()
        uri = await store.store(large_document)
        summary = await store.load(uri, ArtifactSection.SUMMARY)
        full = await store.load(uri, ArtifactSection.FULL)

    Thresholds:
        SUMMARY_THRESHOLD_BYTES: Content size triggering summarization (5KB)
        SUMMARY_MAX_CHARS: Maximum summary length (2000)
        DEFAULT_FIRST_N_CHARS: Default preview length (5000)
    """

    SUMMARY_THRESHOLD_BYTES = 5000  # Summarize content >5KB
    SUMMARY_MAX_CHARS = 2000
    DEFAULT_FIRST_N_CHARS = 5000

    def __init__(self) -> None:
        """Initialize empty artifact store.

        Note: Currently in-memory only. Future: Redis/S3 backend.
        """
        self._artifacts: dict[str, Artifact] = {}

    async def store(
        self,
        content: str,
        artifact_id: str | None = None,
    ) -> str:
        """Store content with automatic section extraction.

        Args:
            content: Content to store (any size)
            artifact_id: Optional custom ID (defaults to content hash)

        Returns:
            URI reference (artifact://<id>)
        """
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        artifact_id = artifact_id or content_hash
        uri = f"artifact://{artifact_id}"

        # Extract sections for selective loading
        artifact = Artifact(
            uri=uri,
            full_content=content,
            summary=(
                self._generate_summary(content)
                if len(content.encode()) > self.SUMMARY_THRESHOLD_BYTES
                else None
            ),
            code_blocks=self._extract_code_blocks(content),
            headings=self._extract_headings(content),
            size_bytes=len(content.encode()),
            content_hash=content_hash,
        )

        self._artifacts[uri] = artifact
        return uri

    async def load(
        self,
        uri: str,
        section: ArtifactSection = ArtifactSection.SUMMARY,
    ) -> str:
        """Load specific section from artifact.

        Args:
            uri: Artifact URI (from store())
            section: Which section to load

        Returns:
            Requested section content

        Raises:
            ValueError: If artifact not found
        """
        artifact = self._artifacts.get(uri)
        if not artifact:
            raise ValueError(f"Artifact not found: {uri}")

        if section == ArtifactSection.FULL:
            return artifact.full_content
        elif section == ArtifactSection.SUMMARY:
            return artifact.summary or artifact.full_content[: self.SUMMARY_MAX_CHARS]
        elif section == ArtifactSection.FIRST_N:
            return artifact.full_content[: self.DEFAULT_FIRST_N_CHARS]
        elif section == ArtifactSection.CODE_BLOCKS:
            return "\n\n".join(artifact.code_blocks)
        elif section == ArtifactSection.HEADINGS:
            return "\n".join(artifact.headings)

        # Fallback for unknown section
        return artifact.summary or artifact.full_content[: self.SUMMARY_MAX_CHARS]

    def get_metadata(self, uri: str) -> dict[str, int | str]:
        """Get artifact metadata without loading content.

        Args:
            uri: Artifact URI

        Returns:
            Metadata dict with size_bytes, content_hash, etc.

        Raises:
            ValueError: If artifact not found
        """
        artifact = self._artifacts.get(uri)
        if not artifact:
            raise ValueError(f"Artifact not found: {uri}")

        return {
            "size_bytes": artifact.size_bytes,
            "content_hash": artifact.content_hash,
            "has_summary": artifact.summary is not None,
            "code_blocks_count": len(artifact.code_blocks),
            "headings_count": len(artifact.headings),
        }

    def delete(self, uri: str) -> bool:
        """Delete artifact from store.

        Args:
            uri: Artifact URI

        Returns:
            True if deleted, False if not found
        """
        if uri in self._artifacts:
            del self._artifacts[uri]
            return True
        return False

    def _extract_code_blocks(self, content: str) -> list[str]:
        """Extract fenced code blocks from markdown.

        Args:
            content: Markdown content

        Returns:
            List of code block contents (without fence markers)
        """
        pattern = r"```[\w]*\n(.*?)```"
        return re.findall(pattern, content, re.DOTALL)

    def _extract_headings(self, content: str) -> list[str]:
        """Extract markdown headings for document outline.

        Args:
            content: Markdown content

        Returns:
            List of heading texts (without # markers)
        """
        pattern = r"^#{1,6}\s+(.+)$"
        return re.findall(pattern, content, re.MULTILINE)

    def _generate_summary(self, content: str) -> str:
        """Generate summary for large content.

        Currently: Simple truncation to first N chars.
        Future: LLM-based summarization for better quality.

        Args:
            content: Content to summarize

        Returns:
            Summary string (max SUMMARY_MAX_CHARS)
        """
        if len(content) > self.SUMMARY_MAX_CHARS:
            return content[: self.SUMMARY_MAX_CHARS] + "..."
        return content
