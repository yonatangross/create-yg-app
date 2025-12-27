# Context Engineering Implementation Checklist

## Pre-Implementation

- [ ] Review current memory architecture
- [ ] Identify context window limits for target models
- [ ] Audit existing token usage patterns
- [ ] Set up Langfuse for observability

---

## Token Management

### Token Counting
- [ ] Add `tiktoken` dependency
- [ ] Create `TokenCounter` class with `cl100k_base` encoding
- [ ] Implement `count_tokens(text: str) -> int`
- [ ] Implement `truncate_to_tokens(text: str, max_tokens: int) -> str`
- [ ] Add unit tests for Unicode, code, mixed content

### Token Budget
- [ ] Define `ContextBudget` config class
- [ ] Set default budget = 6000 tokens (75% of 8K)
- [ ] Reserve 2000 tokens for response
- [ ] Implement token-based sliding window
- [ ] Add budget logging for monitoring

---

## Embedding Service

### Core Implementation
- [ ] Use `text-embedding-3-small` (1536 dims)
- [ ] Implement L2 normalization
- [ ] Use token-based truncation (8000 max)
- [ ] Add retry with exponential backoff
- [ ] Cache frequently-used embeddings

### Quality Checks
- [ ] Verify dimension = 1536
- [ ] Test normalization: `||v|| ≈ 1.0`
- [ ] Benchmark against character truncation
- [ ] Test retry on transient failures

---

## Conversation Compaction

### Summarization
- [ ] Create `SessionCompactor` class
- [ ] Define `CompactionConfig` model
- [ ] Implement LLM-based summarization
- [ ] Set trigger threshold (default: 10 turns)
- [ ] Keep recent N turns verbatim (default: 5)

### Tool Preservation
- [ ] Identify tool call messages
- [ ] Identify tool result messages
- [ ] Always include in compacted context
- [ ] Handle long tool results (truncate if needed)

### Testing
- [ ] Test summarization quality
- [ ] Verify compression ratio > 2x
- [ ] Test context continuity across compaction
- [ ] Benchmark token savings

---

## Context Compiler

### Pipeline
- [ ] Create `ContextCompiler` class
- [ ] Implement ordered assembly:
  1. System prompt
  2. Proactive memory
  3. Compacted prefix (summaries)
  4. Recent messages
  5. Current input
- [ ] Return `CompiledContext` with metrics

### Prompt Caching
- [ ] Separate static prefix from dynamic messages
- [ ] Add Anthropic cache control headers
- [ ] Measure cache hit rate
- [ ] Document cost savings

---

## Proactive Recall

### Implementation
- [ ] Create `proactive_recall()` function
- [ ] Set similarity threshold (default: 0.65)
- [ ] Limit results (default: 3)
- [ ] Format for system prompt injection
- [ ] Add timeout handling

### Agent Integration
- [ ] Call before agent invocation
- [ ] Pass via state (`proactive_context` field)
- [ ] Inject before conversation history
- [ ] Log recall success/empty rates

---

## Reactive Memory Tool

### Tool Definition
- [ ] Create `@tool search_memory()`
- [ ] Accept query and optional memory_type
- [ ] Return formatted snippets with scores
- [ ] Document when to use in description

### Registration
- [ ] Add to agent's tool list
- [ ] Test agent decision to use tool
- [ ] Monitor tool call frequency

---

## Observability

### Logging
- [ ] Log token usage per request
- [ ] Log compression ratios
- [ ] Log recall success rates
- [ ] Log context compilation time

### Langfuse Integration
- [ ] Trace context compilation
- [ ] Track embedding costs
- [ ] Monitor memory search latency
- [ ] Alert on context overflow

---

## Testing

### Unit Tests
- [ ] TokenCounter accuracy
- [ ] EmbeddingService normalization
- [ ] SessionCompactor summarization
- [ ] ContextCompiler assembly order

### Integration Tests
- [ ] Full chat flow with memory
- [ ] Multi-turn conversation continuity
- [ ] "What was my first message?" test
- [ ] Context budget enforcement

### Performance Tests
- [ ] Token counting latency < 1ms
- [ ] Embedding generation < 500ms
- [ ] Context compilation < 100ms
- [ ] Proactive recall < 200ms

---

## Documentation

- [ ] Update API docs with memory endpoints
- [ ] Document configuration options
- [ ] Add architecture diagrams
- [ ] Create troubleshooting guide
