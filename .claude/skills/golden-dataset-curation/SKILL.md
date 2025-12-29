---
name: golden-dataset-curation
description: Quality criteria, workflows, and multi-agent analysis patterns for curating high-quality golden dataset entries
version: 2.0.0
author: YG Starter AI Agent Hub
tags: [golden-dataset, curation, quality, multi-agent, langfuse, 2025]
---

# Golden Dataset Curation

**Curate high-quality documents for the golden dataset with multi-agent validation**

## Overview

This skill provides patterns and workflows for **adding new documents** to the golden dataset with thorough quality analysis. It complements `golden-dataset-management` which handles backup/restore.

**When to use this skill:**
- Adding new documents to the golden dataset
- Classifying content types and difficulty levels
- Generating test queries for new documents
- Running multi-agent quality analysis

---

## Content Type Classification

### Supported Types

| Type | Description | Quality Focus |
|------|-------------|---------------|
| `article` | Technical articles, blog posts | Depth, accuracy, actionability |
| `tutorial` | Step-by-step guides | Completeness, clarity, code quality |
| `research_paper` | Academic papers, whitepapers | Rigor, citations, methodology |
| `documentation` | API docs, reference materials | Accuracy, completeness, examples |
| `video_transcript` | Transcribed video content | Structure, coherence, key points |
| `code_repository` | README, code analysis | Code quality, documentation |

### Classification Criteria

```python
# Content Type Decision Tree
def classify_content_type(content: str, source_url: str) -> str:
    """Classify content type based on structure and source."""

    # URL-based hints
    if "arxiv.org" in source_url or "papers" in source_url:
        return "research_paper"
    if "docs." in source_url or "/api/" in source_url:
        return "documentation"
    if "github.com" in source_url:
        return "code_repository"

    # Content-based analysis
    if has_step_by_step_structure(content):
        return "tutorial"
    if has_academic_structure(content):  # Abstract, methodology, results
        return "research_paper"

    # Default
    return "article"
```

---

## Difficulty Classification

### Stratification Levels

| Level | Semantic Complexity | Expected Retrieval Score | Characteristics |
|-------|---------------------|--------------------------|-----------------|
| **trivial** | Direct keyword match | >0.85 | Technical terms, exact phrases |
| **easy** | Common synonyms | >0.70 | Well-known concepts, slight variations |
| **medium** | Paraphrased intent | >0.55 | Conceptual queries, multi-topic |
| **hard** | Multi-hop reasoning | >0.40 | Cross-domain, comparative analysis |
| **adversarial** | Edge cases | Graceful degradation | Robustness tests, off-domain |

### Classification Factors

```python
def classify_difficulty(document: dict) -> str:
    """Classify document difficulty for retrieval testing."""

    factors = {
        "technical_density": count_technical_terms(document["content"]),
        "section_count": len(document.get("sections", [])),
        "cross_references": count_cross_references(document),
        "abstraction_level": assess_abstraction(document),
        "domain_specificity": assess_domain_specificity(document),
    }

    # Scoring rubric
    score = 0
    if factors["technical_density"] > 50:
        score += 2
    if factors["section_count"] > 10:
        score += 1
    if factors["cross_references"] > 5:
        score += 2
    if factors["abstraction_level"] == "high":
        score += 2

    # Map score to difficulty
    if score <= 2:
        return "trivial"
    elif score <= 4:
        return "easy"
    elif score <= 6:
        return "medium"
    elif score <= 8:
        return "hard"
    else:
        return "adversarial"
```

---

## Quality Evaluation Dimensions

### 1. Accuracy (Weight: 0.25)

**What it measures:** Factual correctness, up-to-date information

**Evaluation criteria:**
- Technical claims are verifiable
- Code examples are syntactically correct
- No outdated information (check dates, versions)
- Sources/citations where applicable

**Thresholds:**
- Perfect: 0.95-1.0 (all claims verifiable)
- Acceptable: 0.70-0.94 (minor inaccuracies)
- Failing: <0.70 (significant errors)

### 2. Coherence (Weight: 0.20)

**What it measures:** Logical flow, structure, readability

**Evaluation criteria:**
- Clear introduction and conclusion
- Logical section ordering
- Smooth transitions between topics
- Consistent terminology

**Thresholds:**
- Perfect: 0.90-1.0 (professional quality)
- Acceptable: 0.60-0.89 (readable but rough)
- Failing: <0.60 (confusing structure)

### 3. Depth (Weight: 0.25)

**What it measures:** Thoroughness, detail level, comprehensiveness

**Evaluation criteria:**
- Covers topic comprehensively
- Includes edge cases and caveats
- Provides context and background
- Appropriate level of detail for audience

**Thresholds:**
- Perfect: 0.90-1.0 (exhaustive coverage)
- Acceptable: 0.55-0.89 (covers main points)
- Failing: <0.55 (superficial treatment)

### 4. Relevance (Weight: 0.30)

**What it measures:** Alignment with your application's technical domains

**Example target domains:**
- AI/ML (LangGraph, RAG, agents, embeddings, LLMs)
- Backend (FastAPI, Node.js, PostgreSQL, APIs)
- Frontend (React, TypeScript, Next.js)
- DevOps (Docker, Kubernetes, CI/CD, monitoring)
- Security (OWASP, authentication, encryption)

**Thresholds:**
- Perfect: 0.95-1.0 (core domain, highly relevant)
- Acceptable: 0.70-0.94 (related domain)
- Failing: <0.70 (off-topic for your use case)

---

## Multi-Agent Analysis Pipeline

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CURATION PIPELINE                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  INPUT: URL/Content                                             │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │  FETCH AGENT    │  WebFetch or file read                     │
│  │  (sequential)   │  Extract structure, detect type            │
│  └────────┬────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  PARALLEL ANALYSIS AGENTS                                │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌──────────┐│   │
│  │  │ Quality   │ │ Difficulty│ │ Domain    │ │ Query    ││   │
│  │  │ Evaluator │ │ Classifier│ │ Tagger    │ │ Generator││   │
│  │  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └────┬─────┘│   │
│  │        │             │             │            │       │   │
│  └────────┼─────────────┼─────────────┼────────────┼───────┘   │
│           │             │             │            │            │
│           └─────────────┼─────────────┼────────────┘            │
│                         ▼             │                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  CONSENSUS AGGREGATOR                                    │   │
│  │  • Weighted quality score                                │   │
│  │  • Confidence level (agent agreement)                    │   │
│  │  • Final recommendation: include/review/exclude          │   │
│  └────────┬────────────────────────────────────────────────┘   │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │  USER APPROVAL  │  Show scores, get confirmation             │
│  └────────┬────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  OUTPUT: Curated document entry                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Agent Specifications

#### Quality Evaluator Agent

```python
Task(
    subagent_type="code-quality-reviewer",
    prompt="""GOLDEN DATASET QUALITY EVALUATION

    Evaluate this content for golden dataset inclusion:

    Content: {content_preview}
    Source: {source_url}
    Type: {content_type}

    Score these dimensions (0.0-1.0):

    1. ACCURACY (weight 0.25)
       - Technical correctness
       - Code validity
       - Up-to-date information

    2. COHERENCE (weight 0.20)
       - Logical structure
       - Clear flow
       - Consistent terminology

    3. DEPTH (weight 0.25)
       - Comprehensive coverage
       - Edge cases mentioned
       - Appropriate detail level

    4. RELEVANCE (weight 0.30)
       - Alignment with AI/ML, backend, frontend, DevOps
       - Practical applicability
       - Technical value

    Output JSON:
    {
        "accuracy": {"score": 0.X, "rationale": "..."},
        "coherence": {"score": 0.X, "rationale": "..."},
        "depth": {"score": 0.X, "rationale": "..."},
        "relevance": {"score": 0.X, "rationale": "..."},
        "weighted_total": 0.X,
        "recommendation": "include|review|exclude"
    }
    """,
    run_in_background=True
)
```

#### Difficulty Classifier Agent

```python
Task(
    subagent_type="Explore",
    prompt="""DIFFICULTY CLASSIFICATION

    Analyze document complexity for retrieval testing:

    Content: {content_preview}
    Sections: {section_titles}

    Assess these factors:
    1. Technical term density (count specialized terms)
    2. Section complexity (nesting depth, count)
    3. Cross-domain references (links between topics)
    4. Abstraction level (concrete vs conceptual)
    5. Query ambiguity potential (how many ways to ask about this?)

    Output JSON:
    {
        "difficulty": "trivial|easy|medium|hard|adversarial",
        "factors": {
            "technical_density": "low|medium|high",
            "structure_complexity": "simple|moderate|complex",
            "cross_references": "none|some|many",
            "abstraction": "concrete|mixed|abstract"
        },
        "expected_retrieval_score": 0.X,
        "rationale": "..."
    }
    """
)
```

#### Domain Tagger Agent

```python
Task(
    subagent_type="Explore",
    prompt="""DOMAIN TAGGING

    Extract domain tags for this content:

    Content: {content_preview}
    Source: {source_url}

    Primary domains (pick 1-2):
    - ai-ml (LLM, agents, RAG, embeddings, LangGraph)
    - backend (FastAPI, PostgreSQL, APIs, microservices)
    - frontend (React, TypeScript, UI/UX)
    - devops (Docker, K8s, CI/CD, infrastructure)
    - security (auth, OWASP, encryption)
    - databases (SQL, NoSQL, vector DBs)
    - testing (pytest, playwright, TDD)

    Secondary tags (pick 3-5):
    - Specific technologies mentioned
    - Patterns/concepts covered
    - Use cases addressed

    Output JSON:
    {
        "primary_domains": ["ai-ml", "backend"],
        "tags": ["langraph", "agents", "tool-use", "fastapi"],
        "confidence": 0.X
    }
    """
)
```

#### Query Generator Agent

```python
Task(
    subagent_type="Explore",
    prompt="""TEST QUERY GENERATION

    Generate test queries for this golden dataset document:

    Document ID: {document_id}
    Title: {title}
    Sections: {section_titles}
    Content preview: {content_preview}

    Generate 3-5 test queries with varied difficulty:

    1. At least 1 TRIVIAL query (exact keyword match)
    2. At least 1 EASY query (synonyms, common terms)
    3. At least 1 MEDIUM query (paraphrased intent)
    4. Optional: 1 HARD query (cross-section reasoning)

    For each query specify:
    - Query text
    - Expected sections to match
    - Difficulty level
    - Minimum expected score

    Output JSON:
    {
        "queries": [
            {
                "id": "q-{doc-id}-{num}",
                "query": "How to implement X with Y?",
                "difficulty": "medium",
                "expected_chunks": ["section-id-1", "section-id-2"],
                "min_score": 0.55,
                "modes": ["semantic", "hybrid"],
                "category": "specific",
                "description": "Tests retrieval of X implementation details"
            }
        ]
    }
    """
)
```

---

## Consensus Aggregation

### Aggregation Logic

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class CurationConsensus:
    """Aggregated result from multi-agent analysis."""

    quality_score: float  # Weighted average (0-1)
    confidence: float     # Agent agreement (0-1)
    decision: Literal["include", "review", "exclude"]

    # Individual scores
    accuracy: float
    coherence: float
    depth: float
    relevance: float

    # Classification results
    content_type: str
    difficulty: str
    tags: list[str]

    # Generated queries
    suggested_queries: list[dict]

    # Warnings
    warnings: list[str]

def aggregate_results(
    quality_result: dict,
    difficulty_result: dict,
    domain_result: dict,
    query_result: dict,
) -> CurationConsensus:
    """Aggregate multi-agent results into consensus."""

    # Calculate weighted quality score
    q = quality_result
    quality_score = (
        q["accuracy"]["score"] * 0.25 +
        q["coherence"]["score"] * 0.20 +
        q["depth"]["score"] * 0.25 +
        q["relevance"]["score"] * 0.30
    )

    # Calculate confidence (variance-based)
    scores = [
        q["accuracy"]["score"],
        q["coherence"]["score"],
        q["depth"]["score"],
        q["relevance"]["score"],
    ]
    variance = sum((s - quality_score)**2 for s in scores) / len(scores)
    confidence = 1.0 - min(variance * 4, 1.0)  # Scale variance to confidence

    # Decision thresholds
    if quality_score >= 0.75 and confidence >= 0.7:
        decision = "include"
    elif quality_score >= 0.55:
        decision = "review"
    else:
        decision = "exclude"

    # Collect warnings
    warnings = []
    if q["accuracy"]["score"] < 0.6:
        warnings.append("Low accuracy score - verify technical claims")
    if q["relevance"]["score"] < 0.7:
        warnings.append("Low relevance - may be off-topic for your application")
    if domain_result["confidence"] < 0.7:
        warnings.append("Low confidence in domain classification")

    return CurationConsensus(
        quality_score=quality_score,
        confidence=confidence,
        decision=decision,
        accuracy=q["accuracy"]["score"],
        coherence=q["coherence"]["score"],
        depth=q["depth"]["score"],
        relevance=q["relevance"]["score"],
        content_type=difficulty_result.get("content_type", "article"),
        difficulty=difficulty_result["difficulty"],
        tags=domain_result["tags"],
        suggested_queries=query_result["queries"],
        warnings=warnings,
    )
```

---

## Langfuse Integration

### Trace Structure

```python
# Langfuse trace for curation workflow
trace = langfuse.trace(
    name="golden-dataset-curation",
    metadata={
        "source_url": url,
        "document_id": doc_id,
    }
)

# Spans for each agent
with trace.span(name="fetch_content") as span:
    content = fetch_url(url)
    span.update(output={"length": len(content)})

with trace.span(name="quality_evaluation") as span:
    quality_result = await run_quality_agent(content)
    span.update(output=quality_result)
    # Log individual dimension scores
    trace.score(name="accuracy", value=quality_result["accuracy"]["score"])
    trace.score(name="coherence", value=quality_result["coherence"]["score"])
    trace.score(name="depth", value=quality_result["depth"]["score"])
    trace.score(name="relevance", value=quality_result["relevance"]["score"])

# Final aggregated score
trace.score(name="quality_total", value=consensus.quality_score)
trace.event(
    name="curation_decision",
    metadata={"decision": consensus.decision}
)
```

### Prompt Management

All curation prompts are managed in Langfuse:

| Prompt Name | Purpose | Tags |
|-------------|---------|------|
| `golden-content-classifier` | Classify content_type | `golden-dataset`, `classification` |
| `golden-difficulty-classifier` | Assign difficulty | `golden-dataset`, `difficulty` |
| `golden-domain-tagger` | Extract tags | `golden-dataset`, `tagging` |
| `golden-query-generator` | Generate queries | `golden-dataset`, `query-gen` |

---

## Best Practices

### 1. Quality Thresholds

```yaml
# Recommended thresholds for golden dataset inclusion
minimum_quality_score: 0.70
minimum_confidence: 0.65
required_tags: 2  # At least 2 domain tags
required_queries: 3  # At least 3 test queries
```

### 2. Coverage Balance

Maintain balanced coverage across:
- Content types (don't over-index on articles)
- Difficulty levels (need trivial AND hard)
- Domains (spread across AI/ML, backend, frontend, etc.)

### 3. Duplicate Prevention

Before adding:
1. Check URL against existing `source_url_map.json`
2. Run semantic similarity against existing document embeddings
3. Warn if >80% similar to existing document

### 4. Provenance Tracking

Always record:
- Source URL (canonical)
- Curation date
- Agent scores (for audit trail)
- Langfuse trace ID

---

## Related Skills

- `golden-dataset-management` - Backup/restore operations
- `golden-dataset-validation` - Validation rules and checks
- `langfuse-observability` - Tracing patterns
- `pgvector-search` - Duplicate detection

---

## JSON Schema Validation (2025 Best Practice)

### Document Schema with Strict Validation

```typescript
// Use Zod or JSON Schema for runtime validation
import { z } from 'zod';

export const documentSchema = z.object({
  id: z.string().regex(/^[a-z0-9-]+$/),
  title: z.string().min(10).max(200),
  source_url: z.string().url(),
  content_type: z.enum(['article', 'tutorial', 'research_paper', 'documentation', 'video_transcript', 'code_repository']),
  tags: z.array(z.string()).min(2).max(10),
  sections: z.array(z.object({
    id: z.string(),
    title: z.string(),
    content: z.string().min(50),
    embedding_metadata: z.object({
      model: z.string(),
      dimensions: z.number(),
      generated_at: z.string().datetime(),
    }).optional(),
  })).min(1),
  metadata: z.object({
    quality_score: z.number().min(0).max(1),
    difficulty: z.enum(['trivial', 'easy', 'medium', 'hard', 'adversarial']),
    curation_date: z.string().datetime(),
    langfuse_trace_id: z.string().optional(),
  }),
});

type Document = z.infer<typeof documentSchema>;
```

### Embedding Quality Metrics (2025)

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class EmbeddingQualityMetrics:
    """Track embedding quality for golden dataset."""

    model_name: str  # e.g., "text-embedding-3-large"
    model_version: str
    dimensions: int
    normalization: Literal["l2", "none"]

    # Quality metrics
    avg_magnitude: float  # Should be ~1.0 for normalized
    std_magnitude: float  # Should be ~0 for normalized
    sparsity: float  # % of near-zero values (0-1)

    # Performance
    generation_time_ms: float
    batch_size: int

    def validate(self) -> list[str]:
        """Validate embedding quality."""
        warnings = []

        if self.normalization == "l2":
            if abs(self.avg_magnitude - 1.0) > 0.01:
                warnings.append(f"L2 normalized embeddings should have avg magnitude ~1.0, got {self.avg_magnitude}")
            if self.std_magnitude > 0.1:
                warnings.append(f"High variance in magnitudes: {self.std_magnitude}")

        if self.sparsity > 0.8:
            warnings.append(f"High sparsity ({self.sparsity:.1%}) may indicate low-quality embeddings")

        if self.generation_time_ms > 1000:
            warnings.append(f"Slow embedding generation: {self.generation_time_ms}ms")

        return warnings
```

### Data Versioning (2025 Best Practice)

```python
from datetime import datetime
from typing import Literal
import hashlib

@dataclass
class DatasetVersion:
    """Track dataset versions for reproducibility."""

    version: str  # Semantic versioning: "2.1.0"
    created_at: datetime

    # Content hash for integrity
    content_hash: str  # SHA256 of all documents

    # Model info
    embedding_model: str
    embedding_dimensions: int

    # Statistics
    total_documents: int
    total_chunks: int
    total_queries: int

    # Quality metrics
    avg_quality_score: float
    pass_rate: float  # Retrieval test pass rate

    # Changes from previous version
    changelog: list[dict]  # [{"action": "added", "count": 5, "description": "..."}]

    @staticmethod
    def calculate_content_hash(documents: list[dict]) -> str:
        """Calculate reproducible content hash."""
        # Sort documents by ID for deterministic hash
        sorted_docs = sorted(documents, key=lambda d: d["id"])
        content = json.dumps(sorted_docs, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def save_to_file(self, path: Path):
        """Save version metadata."""
        with open(path, "w") as f:
            json.dump({
                "version": self.version,
                "created_at": self.created_at.isoformat(),
                "content_hash": self.content_hash,
                "embedding_model": self.embedding_model,
                "embedding_dimensions": self.embedding_dimensions,
                "statistics": {
                    "documents": self.total_documents,
                    "chunks": self.total_chunks,
                    "queries": self.total_queries,
                },
                "quality": {
                    "avg_quality_score": self.avg_quality_score,
                    "pass_rate": self.pass_rate,
                },
                "changelog": self.changelog,
            }, f, indent=2)
```

---

**Version:** 2.0.0 (January 2025)
**Updated:** Modern patterns for AI/ML dataset curation
