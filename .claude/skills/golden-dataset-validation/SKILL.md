---
name: golden-dataset-validation
description: Validation rules, schema checks, duplicate detection, and coverage analysis for golden dataset integrity
version: 2.0.0
author: YG Starter AI Agent Hub
tags: [golden-dataset, validation, integrity, schema, duplicate-detection, 2025]
---

# Golden Dataset Validation

**Ensure data integrity, prevent duplicates, and maintain quality standards**

## Overview

This skill provides comprehensive validation patterns for the golden dataset, ensuring every entry meets quality standards before inclusion.

**When to use this skill:**
- Validating new documents before adding
- Running integrity checks on existing dataset
- Detecting duplicate or similar content
- Analyzing coverage gaps
- Pre-commit validation hooks

---

## Schema Validation

### Document Schema (v2.0)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["id", "title", "source_url", "content_type", "sections"],
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^[a-z0-9-]+$",
      "description": "Unique kebab-case identifier"
    },
    "title": {
      "type": "string",
      "minLength": 10,
      "maxLength": 200
    },
    "source_url": {
      "type": "string",
      "format": "uri",
      "description": "Canonical source URL (NOT placeholder)"
    },
    "content_type": {
      "type": "string",
      "enum": ["article", "tutorial", "research_paper", "documentation", "video_transcript", "code_repository"]
    },
    "bucket": {
      "type": "string",
      "enum": ["short", "long"]
    },
    "language": {
      "type": "string",
      "default": "en"
    },
    "tags": {
      "type": "array",
      "items": {"type": "string"},
      "minItems": 2,
      "maxItems": 10
    },
    "sections": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["id", "title", "content"],
        "properties": {
          "id": {"type": "string", "pattern": "^[a-z0-9-/]+$"},
          "title": {"type": "string"},
          "content": {"type": "string", "minLength": 50},
          "granularity": {"enum": ["coarse", "fine", "summary"]}
        }
      }
    }
  }
}
```

### Query Schema

```json
{
  "type": "object",
  "required": ["id", "query", "difficulty", "expected_chunks", "min_score"],
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^q-[a-z0-9-]+$"
    },
    "query": {
      "type": "string",
      "minLength": 5,
      "maxLength": 500
    },
    "modes": {
      "type": "array",
      "items": {"enum": ["semantic", "keyword", "hybrid"]}
    },
    "category": {
      "enum": ["specific", "broad", "negative", "edge", "coarse-to-fine"]
    },
    "difficulty": {
      "enum": ["trivial", "easy", "medium", "hard", "adversarial"]
    },
    "expected_chunks": {
      "type": "array",
      "items": {"type": "string"},
      "minItems": 1
    },
    "min_score": {
      "type": "number",
      "minimum": 0,
      "maximum": 1
    }
  }
}
```

---

## Validation Rules

### Rule 1: No Placeholder URLs

```python
FORBIDDEN_URL_PATTERNS = [
    "project.dev",
    "placeholder",
    "example.com",
    "localhost",
    "127.0.0.1",
]

def validate_url(url: str) -> tuple[bool, str]:
    """Validate URL is not a placeholder."""
    for pattern in FORBIDDEN_URL_PATTERNS:
        if pattern in url.lower():
            return False, f"URL contains forbidden pattern: {pattern}"

    # Must be HTTPS (except for specific cases)
    if not url.startswith("https://"):
        if not url.startswith("http://arxiv.org"):  # arXiv redirects
            return False, "URL must use HTTPS"

    return True, "OK"
```

### Rule 2: Unique Identifiers

```python
def validate_unique_ids(documents: list[dict], queries: list[dict]) -> list[str]:
    """Ensure all IDs are unique across documents and queries."""
    errors = []

    # Document IDs
    doc_ids = [d["id"] for d in documents]
    if len(doc_ids) != len(set(doc_ids)):
        duplicates = [id for id in doc_ids if doc_ids.count(id) > 1]
        errors.append(f"Duplicate document IDs: {set(duplicates)}")

    # Query IDs
    query_ids = [q["id"] for q in queries]
    if len(query_ids) != len(set(query_ids)):
        duplicates = [id for id in query_ids if query_ids.count(id) > 1]
        errors.append(f"Duplicate query IDs: {set(duplicates)}")

    # Section IDs within documents
    for doc in documents:
        section_ids = [s["id"] for s in doc.get("sections", [])]
        if len(section_ids) != len(set(section_ids)):
            errors.append(f"Duplicate section IDs in document: {doc['id']}")

    return errors
```

### Rule 3: Referential Integrity

```python
def validate_references(documents: list[dict], queries: list[dict]) -> list[str]:
    """Ensure query expected_chunks reference valid section IDs."""
    errors = []

    # Build set of all valid section IDs
    valid_sections = set()
    for doc in documents:
        for section in doc.get("sections", []):
            valid_sections.add(section["id"])

    # Check query references
    for query in queries:
        for chunk_id in query.get("expected_chunks", []):
            if chunk_id not in valid_sections:
                errors.append(
                    f"Query {query['id']} references invalid section: {chunk_id}"
                )

    return errors
```

### Rule 4: Content Quality

```python
def validate_content_quality(document: dict) -> list[str]:
    """Validate document content meets quality standards."""
    warnings = []

    # Title length
    title = document.get("title", "")
    if len(title) < 10:
        warnings.append("Title too short (min 10 chars)")
    if len(title) > 200:
        warnings.append("Title too long (max 200 chars)")

    # Section content
    for section in document.get("sections", []):
        content = section.get("content", "")
        if len(content) < 50:
            warnings.append(f"Section {section['id']} content too short (min 50 chars)")
        if len(content) > 50000:
            warnings.append(f"Section {section['id']} content very long (>50k chars)")

    # Tags
    tags = document.get("tags", [])
    if len(tags) < 2:
        warnings.append("Too few tags (min 2)")
    if len(tags) > 10:
        warnings.append("Too many tags (max 10)")

    return warnings
```

### Rule 5: Difficulty Distribution

```python
def validate_difficulty_distribution(queries: list[dict]) -> list[str]:
    """Ensure balanced difficulty distribution."""
    warnings = []

    # Count by difficulty
    distribution = {}
    for query in queries:
        diff = query.get("difficulty", "unknown")
        distribution[diff] = distribution.get(diff, 0) + 1

    # Minimum requirements
    requirements = {
        "trivial": 3,
        "easy": 3,
        "medium": 5,  # Most common real-world case
        "hard": 3,
    }

    for level, min_count in requirements.items():
        actual = distribution.get(level, 0)
        if actual < min_count:
            warnings.append(
                f"Insufficient {level} queries: {actual}/{min_count}"
            )

    return warnings
```

---

## Duplicate Detection

### Semantic Similarity Check

```python
import numpy as np
from typing import Optional

async def check_duplicate(
    new_content: str,
    existing_embeddings: list[tuple[str, np.ndarray]],
    embedding_service,
    threshold: float = 0.85,
) -> Optional[tuple[str, float]]:
    """Check if content is duplicate of existing document.

    Args:
        new_content: Content to check
        existing_embeddings: List of (doc_id, embedding) tuples
        embedding_service: Service to generate embeddings
        threshold: Similarity threshold for duplicate warning

    Returns:
        (doc_id, similarity) if duplicate found, None otherwise
    """
    # Generate embedding for new content
    new_embedding = await embedding_service.generate_embedding(
        text=new_content[:8000],  # Truncate for embedding
        normalize=True,
    )
    new_vec = np.array(new_embedding)

    # Compare against existing
    max_similarity = 0.0
    most_similar_doc = None

    for doc_id, existing_vec in existing_embeddings:
        # Cosine similarity (vectors are normalized)
        similarity = np.dot(new_vec, existing_vec)

        if similarity > max_similarity:
            max_similarity = similarity
            most_similar_doc = doc_id

    if max_similarity >= threshold:
        return (most_similar_doc, max_similarity)

    return None
```

### URL Duplicate Check

```python
def check_url_duplicate(
    new_url: str,
    source_url_map: dict[str, str],
) -> Optional[str]:
    """Check if URL already exists in dataset.

    Returns document ID if duplicate found.
    """
    # Normalize URL
    normalized = normalize_url(new_url)

    for doc_id, existing_url in source_url_map.items():
        if normalize_url(existing_url) == normalized:
            return doc_id

    return None

def normalize_url(url: str) -> str:
    """Normalize URL for comparison."""
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(url.lower())

    # Remove trailing slashes, www prefix
    netloc = parsed.netloc.replace("www.", "")
    path = parsed.path.rstrip("/")

    # Remove common tracking parameters
    # (simplified - real implementation would parse query string)

    return urlunparse((
        parsed.scheme,
        netloc,
        path,
        "",  # params
        "",  # query (stripped)
        "",  # fragment
    ))
```

---

## Coverage Analysis

### Gap Detection

```python
def analyze_coverage_gaps(
    documents: list[dict],
    queries: list[dict],
) -> dict:
    """Analyze dataset coverage and identify gaps."""

    # Content type distribution
    content_types = {}
    for doc in documents:
        ct = doc.get("content_type", "unknown")
        content_types[ct] = content_types.get(ct, 0) + 1

    # Domain/tag distribution
    all_tags = []
    for doc in documents:
        all_tags.extend(doc.get("tags", []))
    tag_counts = {}
    for tag in all_tags:
        tag_counts[tag] = tag_counts.get(tag, 0) + 1

    # Difficulty distribution
    difficulties = {}
    for query in queries:
        diff = query.get("difficulty", "unknown")
        difficulties[diff] = difficulties.get(diff, 0) + 1

    # Identify gaps
    gaps = []

    # Check content type balance
    total_docs = len(documents)
    if content_types.get("tutorial", 0) / total_docs < 0.15:
        gaps.append("Under-represented: tutorials (<15%)")
    if content_types.get("research_paper", 0) / total_docs < 0.05:
        gaps.append("Under-represented: research papers (<5%)")

    # Check domain coverage
    expected_domains = ["ai-ml", "backend", "frontend", "devops", "security"]
    for domain in expected_domains:
        if tag_counts.get(domain, 0) < 5:
            gaps.append(f"Under-represented domain: {domain} (<5 docs)")

    # Check difficulty balance
    total_queries = len(queries)
    if difficulties.get("hard", 0) / total_queries < 0.10:
        gaps.append("Under-represented: hard queries (<10%)")
    if difficulties.get("adversarial", 0) / total_queries < 0.05:
        gaps.append("Under-represented: adversarial queries (<5%)")

    return {
        "content_type_distribution": content_types,
        "tag_distribution": dict(sorted(tag_counts.items(), key=lambda x: -x[1])[:20]),
        "difficulty_distribution": difficulties,
        "gaps": gaps,
        "total_documents": total_docs,
        "total_queries": total_queries,
    }
```

---

## Validation Workflow

### Pre-Addition Validation

```python
async def validate_before_add(
    document: dict,
    existing_documents: list[dict],
    existing_queries: list[dict],
    source_url_map: dict[str, str],
    embedding_service,
) -> dict:
    """Run full validation before adding document.

    Returns:
        {
            "valid": bool,
            "errors": list[str],  # Blocking issues
            "warnings": list[str],  # Non-blocking issues
            "duplicate_check": {
                "is_duplicate": bool,
                "similar_to": str | None,
                "similarity": float | None,
            }
        }
    """
    errors = []
    warnings = []

    # 1. Schema validation
    schema_errors = validate_schema(document)
    errors.extend(schema_errors)

    # 2. URL validation
    url_valid, url_msg = validate_url(document.get("source_url", ""))
    if not url_valid:
        errors.append(url_msg)

    # 3. URL duplicate check
    url_dup = check_url_duplicate(document.get("source_url", ""), source_url_map)
    if url_dup:
        errors.append(f"URL already exists in dataset as: {url_dup}")

    # 4. Content quality
    quality_warnings = validate_content_quality(document)
    warnings.extend(quality_warnings)

    # 5. Semantic duplicate check
    content = " ".join(
        s.get("content", "") for s in document.get("sections", [])
    )
    existing_embeddings = await load_existing_embeddings(existing_documents)
    dup_result = await check_duplicate(
        content, existing_embeddings, embedding_service
    )

    duplicate_check = {
        "is_duplicate": dup_result is not None,
        "similar_to": dup_result[0] if dup_result else None,
        "similarity": dup_result[1] if dup_result else None,
    }

    if dup_result and dup_result[1] >= 0.90:
        errors.append(
            f"Content too similar to existing document: {dup_result[0]} "
            f"(similarity: {dup_result[1]:.2f})"
        )
    elif dup_result and dup_result[1] >= 0.80:
        warnings.append(
            f"Content similar to existing document: {dup_result[0]} "
            f"(similarity: {dup_result[1]:.2f})"
        )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "duplicate_check": duplicate_check,
    }
```

### Full Dataset Validation

```python
async def validate_full_dataset() -> dict:
    """Run comprehensive validation on entire dataset.

    Use this for:
    - Pre-commit hooks
    - CI/CD validation
    - Periodic integrity checks
    """
    from backend.tests.smoke.retrieval.fixtures.loader import FixtureLoader

    loader = FixtureLoader(use_expanded=True)
    documents = loader.load_documents()
    queries = loader.load_queries()
    source_url_map = loader.load_source_url_map()

    all_errors = []
    all_warnings = []

    # 1. Schema validation for all documents
    for doc in documents:
        errors = validate_schema(doc)
        all_errors.extend([f"[{doc['id']}] {e}" for e in errors])

    # 2. Unique ID validation
    id_errors = validate_unique_ids(documents, queries)
    all_errors.extend(id_errors)

    # 3. Referential integrity
    ref_errors = validate_references(documents, queries)
    all_errors.extend(ref_errors)

    # 4. URL validation
    for doc in documents:
        valid, msg = validate_url(doc.get("source_url", ""))
        if not valid:
            all_errors.append(f"[{doc['id']}] {msg}")

    # 5. Difficulty distribution
    dist_warnings = validate_difficulty_distribution(queries)
    all_warnings.extend(dist_warnings)

    # 6. Coverage analysis
    coverage = analyze_coverage_gaps(documents, queries)
    all_warnings.extend(coverage["gaps"])

    return {
        "valid": len(all_errors) == 0,
        "errors": all_errors,
        "warnings": all_warnings,
        "coverage": coverage,
        "stats": {
            "documents": len(documents),
            "queries": len(queries),
            "sections": sum(len(d.get("sections", [])) for d in documents),
        }
    }
```

---

## CLI Integration

### Validation Commands

```bash
# Validate specific document
uv run python scripts/data/add_to_golden_dataset.py validate \
    --document-id "new-doc-id"

# Validate full dataset
uv run python scripts/data/add_to_golden_dataset.py validate-all

# Check for duplicates
uv run python scripts/data/add_to_golden_dataset.py check-duplicate \
    --url "https://example.com/article"

# Analyze coverage gaps
uv run python scripts/data/add_to_golden_dataset.py coverage
```

---

## Pre-Commit Hook

```bash
#!/bin/bash
# .claude/hooks/pretool/bash/validate-golden-dataset.sh

# Only run if golden dataset files changed
CHANGED_FILES=$(git diff --cached --name-only)

if echo "$CHANGED_FILES" | grep -q "fixtures/documents_expanded.json\|fixtures/queries.json\|fixtures/source_url_map.json"; then
    echo "🔍 Validating golden dataset changes..."

    cd backend
    uv run python scripts/data/add_to_golden_dataset.py validate-all

    if [ $? -ne 0 ]; then
        echo "❌ Golden dataset validation failed!"
        echo "Fix errors before committing."
        exit 1
    fi

    echo "✅ Golden dataset validation passed"
fi
```

---

## Related Skills

- `golden-dataset-curation` - Quality criteria and workflows
- `golden-dataset-management` - Backup/restore operations
- `pgvector-search` - Embedding-based duplicate detection

---

## 2025 Best Practices: Advanced Validation

### Automated Schema Evolution Checking

```python
from typing import Any
import jsonschema

class SchemaEvolutionValidator:
    """Detect breaking changes in schema versions."""

    def __init__(self, schema_v1: dict, schema_v2: dict):
        self.schema_v1 = schema_v1
        self.schema_v2 = schema_v2

    def check_backward_compatibility(self) -> list[str]:
        """Check if v2 schema is backward compatible with v1."""
        issues = []

        # Check required fields
        v1_required = set(self.schema_v1.get("required", []))
        v2_required = set(self.schema_v2.get("required", []))

        new_required = v2_required - v1_required
        if new_required:
            issues.append(f"Breaking: New required fields added: {new_required}")

        # Check removed properties
        v1_props = set(self.schema_v1.get("properties", {}).keys())
        v2_props = set(self.schema_v2.get("properties", {}).keys())

        removed = v1_props - v2_props
        if removed:
            issues.append(f"Breaking: Properties removed: {removed}")

        # Check type changes
        for prop in v1_props & v2_props:
            v1_type = self.schema_v1["properties"][prop].get("type")
            v2_type = self.schema_v2["properties"][prop].get("type")
            if v1_type != v2_type:
                issues.append(f"Breaking: Type changed for '{prop}': {v1_type} -> {v2_type}")

        return issues
```

### Embedding Drift Detection

```python
import numpy as np
from scipy.stats import ks_2samp

class EmbeddingDriftDetector:
    """Detect distribution drift in embeddings."""

    def detect_drift(
        self,
        baseline_embeddings: np.ndarray,
        current_embeddings: np.ndarray,
        threshold: float = 0.05,
    ) -> dict:
        """Detect if embedding distribution has drifted.

        Uses Kolmogorov-Smirnov test on embedding dimensions.
        """
        n_dims = baseline_embeddings.shape[1]
        p_values = []

        for dim in range(n_dims):
            baseline_dim = baseline_embeddings[:, dim]
            current_dim = current_embeddings[:, dim]

            # KS test
            statistic, p_value = ks_2samp(baseline_dim, current_dim)
            p_values.append(p_value)

        # Count significant drifts
        drifted_dims = sum(1 for p in p_values if p < threshold)
        drift_percentage = drifted_dims / n_dims

        return {
            "has_drift": drift_percentage > 0.1,  # >10% dims drifted
            "drifted_dimensions": drifted_dims,
            "total_dimensions": n_dims,
            "drift_percentage": drift_percentage,
            "min_p_value": min(p_values),
            "warning": "Embedding model may have changed" if drift_percentage > 0.1 else None,
        }
```

### Automated Coverage Reports

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class CoverageReport:
    """Comprehensive coverage analysis."""

    # Content type coverage
    content_type_balance: dict[str, float]  # % distribution
    underrepresented_types: list[str]

    # Domain coverage
    domain_balance: dict[str, int]  # count per domain
    missing_domains: list[str]

    # Difficulty coverage
    difficulty_balance: dict[str, int]
    difficulty_gaps: list[str]

    # Query coverage
    total_queries: int
    avg_queries_per_doc: float
    docs_without_queries: list[str]

    # Recommendations
    recommendations: list[str]

    def generate_html_report(self) -> str:
        """Generate HTML coverage report."""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Golden Dataset Coverage Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .metric {{ margin: 20px 0; }}
        .warning {{ color: #d32f2f; }}
        .good {{ color: #388e3c; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f5f5f5; }}
    </style>
</head>
<body>
    <h1>Golden Dataset Coverage Report</h1>

    <div class="metric">
        <h2>Content Type Distribution</h2>
        <table>
            <tr><th>Type</th><th>Percentage</th></tr>
            {''.join(f'<tr><td>{t}</td><td>{p:.1%}</td></tr>' for t, p in self.content_type_balance.items())}
        </table>
        {f'<p class="warning">Underrepresented: {", ".join(self.underrepresented_types)}</p>' if self.underrepresented_types else ''}
    </div>

    <div class="metric">
        <h2>Recommendations</h2>
        <ul>
            {''.join(f'<li>{r}</li>' for r in self.recommendations)}
        </ul>
    </div>
</body>
</html>
        """
```

---

**Version:** 2.0.0 (January 2025)
**Updated:** Modern validation patterns for AI/ML datasets
