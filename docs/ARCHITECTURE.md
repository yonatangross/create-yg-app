# Architecture

> YG Starter - Production-Ready AI Application Template

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                │
│  React 19 + Vite + TanStack + Zustand + Tailwind               │
│  Port: 5183                                                     │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP/SSE
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                         BACKEND                                 │
│  FastAPI + LangGraph + Pydantic                                │
│  Port: 8600                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  API Layer  │  │   Agent     │  │    LLM      │             │
│  │  /api/v1/*  │──│  LangGraph  │──│   Factory   │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└────────┬────────────────┬────────────────┬──────────────────────┘
         │                │                │
         ▼                ▼                ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐
│ PostgreSQL  │  │    Redis    │  │      LLM Providers          │
│ + pgvector  │  │    Cache    │  │  OpenAI / Anthropic / Google│
│ Port: 5447  │  │ Port: 6390  │  └─────────────────────────────┘
└─────────────┘  └─────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                       LANGFUSE                                  │
│  Observability: Tracing, Evaluation, Cost Tracking             │
│  Port: 3010 (Web) + ClickHouse + MinIO + Redis                 │
└─────────────────────────────────────────────────────────────────┘
```

## Technology Stack

### Backend

| Component | Technology | Purpose |
|-----------|------------|---------|
| Framework | FastAPI 0.115+ | Async REST API |
| Validation | Pydantic 2.10+ | Request/response models |
| Agent | LangGraph 0.2+ | Stateful workflows |
| LLM | LangChain 0.3+ | Multi-provider abstraction |
| Database | PostgreSQL 17 + pgvector | Data + vector embeddings |
| Cache | Redis 7 Stack | Caching, rate limiting |
| Observability | Langfuse 2.57+ | LLM tracing |

### Frontend

| Component | Technology | Purpose |
|-----------|------------|---------|
| Framework | React 19 | UI components |
| Build | Vite 6+ | Fast bundling |
| Routing | TanStack Router | Type-safe routing |
| Data | TanStack Query | Server state |
| State | Zustand | Client state |
| Styling | Tailwind CSS | Utility-first CSS |

## Key Patterns

### 1. Multi-Provider LLM Factory

```python
# backend/app/llm/factory.py
class LLMFactory:
    PROVIDER_PRIORITY = ["anthropic", "openai", "google_genai"]

    @classmethod
    def create(cls, model: str | None = None) -> BaseChatModel:
        """Auto-detect provider from available API keys."""
        for provider in cls.PROVIDER_PRIORITY:
            if cls._has_api_key(provider):
                return cls._create_provider(provider, model)
        raise ValueError("No LLM API key configured")

    @classmethod
    def create_with_fallback(cls) -> BaseChatModel:
        """Try providers in order until one succeeds."""
        # Circuit breaker + fallback logic
```

### 2. LangGraph Agent State

```python
# backend/app/agent/state.py
from typing import TypedDict, Annotated
from operator import add

class AgentState(TypedDict):
    query: str
    messages: Annotated[list[BaseMessage], add]  # Accumulates
    retrieved_chunks: Annotated[list[str], add]  # Accumulates
    response: str
    should_retrieve: bool
```

### 3. Circuit Breaker Pattern

```python
# backend/app/core/resilience.py
class CircuitBreaker:
    """3-state circuit breaker: CLOSED → OPEN → HALF_OPEN"""

    async def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError()
        # Execute with failure tracking
```

### 4. Langfuse Observability

```python
from langfuse.decorators import observe

@observe(name="chat_endpoint")
async def chat(request: ChatRequest):
    # Automatically traced with:
    # - Input/output capture
    # - Token usage
    # - Latency
    # - Cost calculation
```

## Database Schema

```sql
-- Core tables (extend as needed)
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

CREATE TABLE messages (
    id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id),
    role VARCHAR(20),
    content TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Vector storage for RAG
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    content TEXT,
    embedding vector(1536),  -- OpenAI ada-002
    metadata JSONB
);

CREATE INDEX ON documents USING ivfflat (embedding vector_cosine_ops);
```

## API Design

### REST Endpoints

```
GET  /api/v1/health          # Health check
POST /api/v1/chat            # Chat with agent (streaming SSE)
POST /api/v1/chat/sync       # Chat with agent (sync response)
```

### SSE Streaming Format

```json
{"event": "thinking", "data": {"step": "routing"}}
{"event": "chunk", "data": {"content": "Hello"}}
{"event": "done", "data": {"usage": {"tokens": 150}}}
```

## Deployment Architecture

```
Production (Docker Compose / K8s)
├── frontend (nginx + static files)
├── backend (uvicorn, 2+ workers)
├── postgres (with pgvector extension)
├── redis (for caching + rate limiting)
└── langfuse (self-hosted observability)
```

## Security Considerations

1. **API Keys**: Never commit to git, use `.env`
2. **Rate Limiting**: SlowAPI middleware on all endpoints
3. **Input Validation**: Pydantic models for all requests
4. **CORS**: Configured for frontend origin only
5. **SQL Injection**: SQLAlchemy ORM prevents injection
6. **XSS**: React's JSX escaping by default

## Performance Optimizations

1. **Async Everywhere**: FastAPI + asyncpg + httpx
2. **Connection Pooling**: SQLAlchemy async pool
3. **Redis Caching**: Semantic cache for LLM responses
4. **Streaming**: SSE for real-time responses
5. **Circuit Breaker**: Fail fast on provider issues

## Port Configuration

All services use offset ports to avoid conflicts with other local projects:

| Service | External Port | Internal Port |
|---------|--------------|---------------|
| Frontend | 5183 | 5173 |
| Backend | 8600 | 8600 |
| PostgreSQL | 5447 | 5432 |
| Redis | 6390 | 6379 |
| Langfuse | 3010 | 3000 |
| MinIO | 9010-9011 | 9000-9001 |

See [CONFIGURATION.md](CONFIGURATION.md) for full port details and multi-project setup.

---

## Related Documents

- `CLAUDE.md` - AI development instructions
- `CONFIGURATION.md` - Port configuration and tuning guide
- `.claude/skills/` - Implementation patterns
- `.claude/instructions/` - Development rules
