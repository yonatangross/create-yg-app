# YG Starter Context Engineering Implementation

## Current State (Before)

```python
# chat.py - Basic implementation
MAX_CONTEXT_MESSAGES = 20  # Message count, not tokens!

@router.post("")
async def chat(request: ChatRequest) -> ChatResponse:
    conversation_id = request.conversation_id or "default"

    # Load history (no token awareness)
    chat_history = get_chat_history(conversation_id)
    messages = await chat_history.aget_messages()

    # Simple sliding window (drops old messages)
    if len(messages) > MAX_CONTEXT_MESSAGES:
        messages = messages[-MAX_CONTEXT_MESSAGES:]  # Lost context!

    # Invoke agent
    result = await agent.ainvoke({
        "query": request.message,
        "messages": messages,
        "proactive_context": proactive_context,
    })

    # Save new messages
    await chat_history.aadd_messages([
        HumanMessage(content=request.message),
        AIMessage(content=result["response"]),
    ])

    return ChatResponse(response=result["response"])
```

**Issues:**
1. Message count != token count
2. No summarization of old messages
3. No tool call preservation
4. No token budget enforcement

---

## Target State (After)

```python
# chat.py - Production implementation
from app.shared.services.context import ContextCompiler, CompactionConfig
from app.shared.services.memory import MemoryService

@router.post("")
async def chat(request: ChatRequest) -> ChatResponse:
    conversation_id = request.conversation_id or "default"

    # 1. Configure context budget
    config = CompactionConfig(
        token_budget=6000,
        max_turns_full=5,
        summarize_after=10,
        preserve_tool_calls=True,
    )

    # 2. Load and compact history
    chat_history = get_chat_history(conversation_id)
    raw_messages = await chat_history.aget_messages()

    compactor = SessionCompactor(config)
    compacted = await compactor.compact(raw_messages)

    # 3. Load proactive context (long-term memory)
    async with get_session() as session:
        memory_service = MemoryService(session)
        proactive_context = await memory_service.proactive_recall(request.message)

    # 4. Compile full context
    compiler = ContextCompiler(compactor)
    context = await compiler.compile(
        system_prompt=SYSTEM_PROMPT,
        history=compacted.messages,
        proactive_context=proactive_context,
        current_input=request.message,
    )

    # 5. Log context metrics
    logger.info(
        "context_compiled",
        original_messages=len(raw_messages),
        compiled_messages=len(compacted.messages),
        compression_ratio=compacted.compression_ratio,
        total_tokens=compacted.total_tokens,
        has_summary=compacted.summary is not None,
    )

    # 6. Invoke agent with compiled context
    result = await agent.ainvoke({
        "query": request.message,
        "messages": context,
        "conversation_id": conversation_id,
    })

    # 7. Save messages and update summary if needed
    await chat_history.aadd_messages([
        HumanMessage(content=request.message),
        AIMessage(content=result["response"]),
    ])

    # Save summary to long-term memory if generated
    if compacted.summary:
        async with get_session() as session:
            memory_service = MemoryService(session)
            await memory_service.save_conversation_summary(
                conversation_id=conversation_id,
                summary=compacted.summary,
                message_count=len(raw_messages),
            )

    return ChatResponse(
        response=result["response"],
        conversation_id=conversation_id,
    )
```

---

## File Structure

```
backend/app/
├── shared/services/
│   ├── context/
│   │   ├── __init__.py
│   │   ├── compiler.py           # ContextCompiler
│   │   ├── compaction.py         # SessionCompactor, CompactionConfig
│   │   └── token_counter.py      # tiktoken integration
│   └── memory/
│       ├── __init__.py
│       ├── memory_service.py     # Store, search, recall
│       └── embedding_service.py  # OpenAI + normalization
├── db/models/
│   └── memory.py                 # AgentMemory, ConversationSummary
└── api/v1/
    └── chat.py                   # Updated endpoint
```

---

## Key Classes

### CompactionConfig

```python
# shared/services/context/compaction.py

class CompactionConfig(BaseModel):
    """Configuration for conversation compaction."""

    max_turns_full: int = Field(
        default=5,
        description="Number of recent turns to keep verbatim"
    )
    summarize_after: int = Field(
        default=10,
        description="Trigger summarization after this many turns"
    )
    summary_max_tokens: int = Field(
        default=500,
        description="Maximum tokens for summary"
    )
    token_budget: int = Field(
        default=6000,
        description="Total token budget for compiled context"
    )
    preserve_tool_calls: bool = Field(
        default=True,
        description="Always include tool calls regardless of age"
    )

    @field_validator('token_budget')
    @classmethod
    def budget_must_exceed_summary(cls, v, info):
        summary_max = info.data.get('summary_max_tokens', 500)
        if v <= summary_max * 2:
            raise ValueError('token_budget must exceed 2x summary_max_tokens')
        return v
```

### SessionCompactor

```python
# shared/services/context/compaction.py

@dataclass
class CompiledContext:
    prefix: list[BaseMessage]
    messages: list[BaseMessage]
    summary: str | None
    original_count: int
    total_tokens: int

    @property
    def compression_ratio(self) -> float:
        compiled_count = len(self.prefix) + len(self.messages)
        return self.original_count / max(compiled_count, 1)


class SessionCompactor:
    """Compact conversation history with summarization."""

    SUMMARY_PROMPT = '''Summarize this conversation concisely:

{messages}

Focus on:
- Key topics discussed
- User preferences expressed
- Important facts learned
- Unresolved questions or tasks

Keep to 2-3 sentences maximum.'''

    def __init__(self, config: CompactionConfig):
        self.config = config
        self.token_counter = TokenCounter()
        self.llm = get_llm()

    async def compact(self, history: list[BaseMessage]) -> CompiledContext:
        """Compact history to fit token budget."""
        original_count = len(history)

        # No compaction needed
        if original_count <= self.config.summarize_after:
            return CompiledContext(
                prefix=[],
                messages=history,
                summary=None,
                original_count=original_count,
                total_tokens=self._count_tokens(history),
            )

        # Extract tool calls (always preserved)
        tool_msgs = [m for m in history if self._is_tool_related(m)]
        regular_msgs = [m for m in history if not self._is_tool_related(m)]

        # Split into older (summarize) and recent (keep)
        cutoff = len(regular_msgs) - self.config.max_turns_full * 2
        older = regular_msgs[:cutoff]
        recent = regular_msgs[cutoff:]

        # Generate summary
        summary = await self._summarize(older)

        # Build prefix
        prefix = []
        if summary:
            prefix.append(SystemMessage(content=f"Previous context: {summary}"))

        # Merge tool calls back into recent (chronologically)
        messages = self._merge_chronologically(recent, tool_msgs)

        return CompiledContext(
            prefix=prefix,
            messages=messages,
            summary=summary,
            original_count=original_count,
            total_tokens=self._count_tokens(prefix + messages),
        )

    async def _summarize(self, messages: list[BaseMessage]) -> str:
        """Generate LLM summary of messages."""
        formatted = self._format_for_summary(messages)
        prompt = self.SUMMARY_PROMPT.format(messages=formatted)

        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        return response.content[:self.config.summary_max_tokens * 4]  # Rough char limit

    def _is_tool_related(self, msg: BaseMessage) -> bool:
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            return True
        if isinstance(msg, ToolMessage):
            return True
        return False
```

### ContextCompiler

```python
# shared/services/context/compiler.py

class ContextCompiler:
    """Compile context for LLM invocation."""

    def __init__(self, compactor: SessionCompactor):
        self.compactor = compactor

    async def compile(
        self,
        system_prompt: str,
        history: list[BaseMessage],
        proactive_context: str,
        current_input: str,
    ) -> list[BaseMessage]:
        """Build ordered context for LLM call."""
        result = []

        # 1. System prompt (always first)
        result.append(SystemMessage(content=system_prompt))

        # 2. Proactive memory context
        if proactive_context:
            result.append(SystemMessage(content=proactive_context))

        # 3. Compact and add history
        compacted = await self.compactor.compact(history)
        result.extend(compacted.prefix)
        result.extend(compacted.messages)

        # 4. Current input (always last)
        result.append(HumanMessage(content=current_input))

        return result
```

---

## Migration Steps

1. **Add dependencies:**
   ```bash
   uv add tiktoken tenacity
   ```

2. **Create context service files**

3. **Update chat.py imports and logic**

4. **Add database migration for ConversationSummary**

5. **Run tests:**
   ```bash
   uv run pytest tests/unit/test_compaction.py -v
   uv run pytest tests/integration/test_chat_memory.py -v
   ```

6. **Monitor in Langfuse:**
   - Track compression ratios
   - Monitor token usage
   - Alert on context overflow
