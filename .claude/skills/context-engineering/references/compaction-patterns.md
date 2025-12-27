# Compaction Patterns Reference

## Overview

Compaction reduces conversation history to fit within token budgets while preserving critical context.

---

## Strategy 1: Sliding Window (Basic)

```python
def sliding_window(messages: list, max_messages: int = 20) -> list:
    """Keep only the most recent messages."""
    return messages[-max_messages:]
```

**Pros:**
- Simple to implement
- Predictable behavior

**Cons:**
- Loses all old context
- No semantic awareness
- Name/preference amnesia

**When to use:** Stateless chatbots, demos

---

## Strategy 2: Token-Based Window

```python
def token_window(messages: list, token_budget: int = 6000) -> list:
    """Keep messages that fit in token budget."""
    total = 0
    result = []
    for msg in reversed(messages):
        tokens = count_tokens(msg.content)
        if total + tokens > token_budget:
            break
        result.insert(0, msg)
        total += tokens
    return result
```

**Pros:**
- Respects actual context limits
- Works with variable message lengths

**Cons:**
- Still loses old context
- No summarization

**When to use:** Simple production apps

---

## Strategy 3: Summarization + Recent (Recommended)

```python
class SessionCompactor:
    """LLM-based summarization with recent message preservation."""

    SUMMARY_PROMPT = '''Summarize this conversation:
{messages}

Focus on: topics, preferences, facts, decisions.
Keep to 2-3 sentences.'''

    async def compact(self, history: list) -> CompiledContext:
        if len(history) <= self.config.summarize_after:
            return CompiledContext(prefix=[], messages=history)

        # Split into old (summarize) and recent (keep)
        cutoff = len(history) - self.config.max_turns_full * 2
        older = history[:cutoff]
        recent = history[cutoff:]

        # Summarize older messages
        summary = await self._summarize(older)

        return CompiledContext(
            prefix=[{"role": "system", "content": f"Previous: {summary}"}],
            messages=recent,
            summary=summary
        )
```

**Pros:**
- Preserves semantic content
- Fits any token budget
- Maintains context continuity

**Cons:**
- LLM cost for summarization
- Possible information loss
- Latency for summarization

**When to use:** Production chat apps, multi-session assistants

---

## Strategy 4: Incremental Summarization

```python
class IncrementalCompactor:
    """Update summary after each interaction."""

    async def update_summary(
        self,
        current_summary: str,
        new_exchange: tuple[str, str]
    ) -> str:
        prompt = f'''Update this conversation summary with new information:

Current summary: {current_summary}

New exchange:
User: {new_exchange[0]}
Assistant: {new_exchange[1]}

Updated summary (preserve key info, add new details):'''

        return await self.llm.ainvoke(prompt)
```

**Pros:**
- No batch summarization needed
- Always up-to-date
- Lower latency per message

**Cons:**
- Risk of drift over time
- Harder to debug
- May lose details progressively

**When to use:** Real-time chat, streaming applications

---

## Strategy 5: Tiered Compaction

```python
class TieredCompactor:
    """Multiple compression tiers based on age."""

    async def compact(self, history: list) -> CompiledContext:
        # Tier 1: Last 5 turns (verbatim)
        tier1 = history[-10:]

        # Tier 2: Turns 6-20 (light summary)
        tier2_raw = history[-40:-10]
        tier2_summary = await self._light_summary(tier2_raw)

        # Tier 3: Older than 20 turns (heavy compression)
        tier3_raw = history[:-40]
        tier3_summary = await self._heavy_summary(tier3_raw)

        return CompiledContext(
            prefix=[
                {"role": "system", "content": f"Older context: {tier3_summary}"},
                {"role": "system", "content": f"Recent context: {tier2_summary}"},
            ],
            messages=tier1
        )
```

**Pros:**
- Graduated information density
- Balances detail vs. coverage
- Handles very long conversations

**Cons:**
- Complex to tune
- Multiple LLM calls
- More testing needed

**When to use:** Long-running agents, complex workflows

---

## Tool Call Preservation

**Critical:** Tool calls must NEVER be dropped.

```python
def preserve_tool_calls(messages: list, budget_remaining: int) -> list:
    """Extract tool calls for guaranteed inclusion."""

    # Separate tool-related from regular messages
    tool_msgs = [m for m in messages if is_tool_related(m)]
    regular_msgs = [m for m in messages if not is_tool_related(m)]

    # Calculate tool message tokens
    tool_tokens = sum(count_tokens(m.content) for m in tool_msgs)

    # Fill remaining budget with regular messages
    regular_budget = budget_remaining - tool_tokens
    windowed_regular = token_window(regular_msgs, regular_budget)

    # Merge back chronologically
    return merge_chronologically(windowed_regular, tool_msgs)

def is_tool_related(msg) -> bool:
    """Check if message is tool call or result."""
    if hasattr(msg, 'tool_calls') and msg.tool_calls:
        return True
    if isinstance(msg, ToolMessage):
        return True
    return False
```

---

## Configuration

```python
class CompactionConfig(BaseModel):
    """Tunable compaction parameters."""

    # Trigger thresholds
    max_turns_full: int = 5       # Recent turns kept verbatim
    summarize_after: int = 10     # Trigger summarization at N turns

    # Size limits
    token_budget: int = 6000      # Total context budget
    summary_max_tokens: int = 500 # Summary size cap

    # Behavior flags
    preserve_tool_calls: bool = True
    use_incremental: bool = False
    enable_tiered: bool = False

    # Quality
    summary_model: str = "gpt-4o-mini"  # Model for summarization
```

---

## Metrics

Track these to tune compaction:

| Metric | Target | Alert If |
|--------|--------|----------|
| Compression ratio | > 2x | < 1.5x |
| Summary coherence | > 0.8 | < 0.6 |
| Context continuity | 100% | Any failure |
| Summarization latency | < 2s | > 5s |
| Token savings | > 30% | < 15% |
