---
name: context-engineering
description: Production-grade LLM context management - token budgets, conversation summarization, compaction, proactive recall, and memory architecture for 2025+ AI applications
version: 1.0.0
author: YG Starter
tags: [context-engineering, memory, summarization, compaction, embeddings, 2025]
---

# Context Engineering

**Master LLM context management for production AI applications**

## Overview

Context engineering is the practice of optimizing what information reaches your LLM within its context window. As Andrej Karpathy says: "LLMs are like operating systems - the context window is RAM."

**When to use this skill:**
- Managing conversation history (short-term memory)
- Implementing semantic recall (long-term memory)
- Optimizing token usage and costs
- Building multi-turn chat applications
- Preventing context overflow and degradation

---

## Core Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         MEMORY ARCHITECTURE                                   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                        SHORT-TERM MEMORY                                │ │
│  │                        (Redis - Session)                                │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐ │ │
│  │  │ Conversation    │  │ Message Buffer  │  │ Working Context         │ │ │
│  │  │ History         │  │ (Last N turns)  │  │ (Current session)       │ │ │
│  │  │ TTL: 7 days     │  │ Sliding window  │  │ Ephemeral state         │ │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                        LONG-TERM MEMORY                                 │ │
│  │                    (PostgreSQL + pgvector)                              │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐ │ │
│  │  │ Conversation    │  │ Semantic Memory │  │ User Preferences        │ │ │
│  │  │ Summaries       │  │ (Vector Search) │  │ (Personalization)       │ │ │
│  │  │ Compressed      │  │ 1536-dim embed  │  │ Learning patterns       │ │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Concepts

### 1. Token Budget Management

**Problem:** Context overflow causes API errors and degraded performance.

**Solution:** Token-based sliding window with budget enforcement.

```python
from pydantic import BaseModel
import tiktoken

class ContextBudget(BaseModel):
    """Token budget configuration."""
    token_budget: int = 6000        # Total for history (75% of 8K)
    response_reserve: int = 2000     # Reserve for generation
    system_prompt_budget: int = 500  # System prompt allocation

class TokenCounter:
    """Accurate token counting with tiktoken."""

    def __init__(self, model: str = "gpt-4"):
        self.encoding = tiktoken.encoding_for_model(model)

    def count(self, text: str) -> int:
        return len(self.encoding.encode(text))

    def truncate(self, text: str, max_tokens: int) -> str:
        tokens = self.encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return self.encoding.decode(tokens[:max_tokens])
```

**Critical:** Never use character-based estimates (1 token != 4 chars).

---

### 2. Conversation Compaction

**Problem:** Old messages get dropped entirely, losing critical context.

**Solution:** Summarize older turns, keep recent verbatim.

```python
@dataclass
class CompactionConfig:
    max_turns_full: int = 5        # Recent turns kept verbatim
    summarize_after: int = 10      # Trigger summarization at N turns
    summary_max_tokens: int = 500  # Summary size cap
    preserve_tool_calls: bool = True
    token_budget: int = 6000

@dataclass
class CompiledContext:
    prefix: list[dict]        # Static: summaries, system prompt (cacheable)
    messages: list[dict]      # Dynamic: recent turns
    summary: str | None

    @property
    def compression_ratio(self) -> float:
        return len(self.messages) / (len(self.prefix) + len(self.messages))
```

**Summarization Prompt:**
```
Summarize this conversation concisely:
{messages}

Focus on:
- Key topics discussed
- User preferences expressed
- Important facts learned
- Unresolved questions

Keep to 2-3 sentences maximum.
```

---

### 3. Proactive vs Reactive Recall

**Proactive Recall:** Automatically inject relevant memories before LLM call.

```python
async def proactive_recall(context: str, limit: int = 3) -> str:
    """Fetch relevant memories for context injection."""
    results = await memory_service.search(context, limit=limit, threshold=0.65)

    if not results:
        return ""

    lines = ["## Relevant Context from Memory\n"]
    for i, r in enumerate(results, 1):
        type_label = r.memory.memory_type.value.replace("_", " ").title()
        lines.append(f"{i}. [{type_label}] {r.memory.content}\n")

    return "\n".join(lines)
```

**Reactive Recall:** Agent queries memory when it recognizes knowledge gaps.

```python
@tool
async def search_memory(query: str, memory_type: str | None = None) -> str:
    """Search long-term memory for relevant information.

    Use when you need to recall specific facts from past conversations.
    """
    results = await memory_service.search(query, memory_type, limit=3)
    return format_for_agent(results)
```

---

### 4. Embedding Best Practices

**Model:** OpenAI text-embedding-3-small (1536 dimensions)

**Critical Requirements:**
1. **L2 Normalization:** Embeddings must be normalized for cosine similarity
2. **Token Truncation:** Use tiktoken, not character limits
3. **Retry Logic:** Exponential backoff for API failures

```python
import math

def normalize_vector(vector: list[float]) -> list[float]:
    """L2 normalize for optimal cosine similarity."""
    norm = math.sqrt(sum(x * x for x in vector))
    return [x / norm for x in vector] if norm > 0 else vector

class EmbeddingService:
    MAX_TOKENS = 8000  # Below 8191 API limit

    async def generate_embedding(self, text: str) -> list[float]:
        # Truncate by tokens
        text = self.truncate_to_tokens(text, self.MAX_TOKENS)

        # Generate embedding
        response = await self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )

        # Normalize
        return normalize_vector(response.data[0].embedding)
```

---

### 5. Context Compiler Pipeline

**Ordered assembly is critical for proper prompt construction.**

```python
class ContextCompiler:
    """Compile context for LLM invocation."""

    async def compile(
        self,
        system_prompt: str,
        history: list[BaseMessage],
        proactive_context: str,
        current_input: str,
    ) -> list[BaseMessage]:
        result = []

        # 1. System prompt (always first)
        result.append(SystemMessage(content=system_prompt))

        # 2. Proactive memory context (before history)
        if proactive_context:
            result.append(SystemMessage(content=proactive_context))

        # 3. Compacted history (prefix + recent)
        compacted = await self.compactor.compact(history)
        if compacted.summary:
            result.append(SystemMessage(content=f"Previous context: {compacted.summary}"))
        result.extend(compacted.messages)

        # 4. Current input (always last)
        result.append(HumanMessage(content=current_input))

        return result
```

---

## 2025 Best Practices

From [LangChain's Context Engineering Guide](https://blog.langchain.com/context-engineering-for-agents/):

### Four Core Strategies

1. **Write Context:** Persist information outside context (scratchpads, memory)
2. **Select Context:** Retrieve only relevant information (RAG, filters)
3. **Compress Context:** Summarize or trim to save space
4. **Order Context:** Structure for optimal model attention

### Common Pitfalls

| Pitfall | Impact | Fix |
|---------|--------|-----|
| Context Poisoning | Hallucinations persist | Validate before storing |
| Context Distraction | Irrelevant info hurts quality | Higher similarity thresholds |
| Context Confusion | Fragmented info degrades 39%! | Keep related content together |
| Context Overflow | API errors, truncation | Token budgets |

### Memory Type Separation

**Critical:** RAG and Memory are NOT the same thing!

| Aspect | RAG (Knowledge) | Memory (Context) |
|--------|-----------------|------------------|
| Source | Curated corpora | Conversational history |
| Goal | Domain expertise | Personalization |
| Update | Periodic | Real-time |
| Governance | Versioned | User-scoped |

---

## Implementation Checklist

### Phase 1: Critical (Production Blockers)

- [ ] Add tiktoken for exact token counting
- [ ] Implement token_budget (default: 6000)
- [ ] Add L2 normalization to embeddings
- [ ] Implement conversation summarization
- [ ] Preserve tool calls in compaction

### Phase 2: High Value

- [ ] Create CompactionConfig for tunability
- [ ] Build ContextCompiler pipeline
- [ ] Add prefix/message split for prompt caching
- [ ] Implement embedding retry with backoff
- [ ] Add reactive memory tool for agents

### Phase 3: Optimization

- [ ] Agent-memory type mapping
- [ ] Relevance decay over time
- [ ] Batch embedding API (50% cost savings)
- [ ] Artifact store for large content
- [ ] Chunking service for documents

---

## File Structure

```
backend/app/
├── shared/services/
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── memory_service.py      # Store, search, proactive_recall
│   │   ├── embedding_service.py   # OpenAI embeddings with normalization
│   │   └── compaction.py          # SessionCompactor, CompactionConfig
│   └── context/
│       ├── __init__.py
│       ├── compiler.py            # ContextCompiler pipeline
│       ├── token_counter.py       # tiktoken integration
│       └── artifact_store.py      # Large content handling
├── db/models/
│   └── memory.py                  # AgentMemory, ConversationSummary
└── api/v1/
    └── chat.py                    # Memory integration points
```

---

## References

### Documentation
- [LangChain Context Engineering](https://blog.langchain.com/context-engineering-for-agents/)
- [FlowHunt 2025 Guide](https://www.flowhunt.io/blog/context-engineering/)
- [RAGFlow 2025 Review](https://ragflow.io/blog/rag-review-2025-from-rag-to-context)

### Related Skills
- `pgvector-search` - Semantic similarity search
- `langgraph-workflows` - Workflow state management
- `langfuse-observability` - Context usage tracking

---

**Version:** 1.0.0 (December 2025)
**Status:** Active development for YG Starter
