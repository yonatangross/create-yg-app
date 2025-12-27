# YG Starter

> Production-ready AI application with multi-provider LLM support, RAG, and full observability.

## Quick Reference

| Resource | Location |
|----------|----------|
| Backend API | `http://localhost:8600/docs` |
| Frontend | `http://localhost:5183` |
| Langfuse | `http://localhost:3010` |

## Technology Stack

### Backend (Python 3.12)
- **Framework**: FastAPI + Pydantic
- **Agent**: LangGraph for multi-step workflows
- **LLM**: Multi-provider (OpenAI, Anthropic, Google)
- **Database**: PostgreSQL 17 + pgvector
- **Cache**: Redis 7 (Stack)
- **Observability**: Langfuse (self-hosted)

### Frontend (React 19)
- **Build**: Vite
- **Router**: TanStack Router
- **Data**: TanStack Query
- **State**: Zustand
- **UI**: Tailwind + Radix UI

## Project Structure

```
yg-starter/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # REST endpoints
│   │   ├── agent/           # LangGraph workflows
│   │   │   ├── graph.py     # Main workflow
│   │   │   ├── state.py     # TypedDict state
│   │   │   ├── nodes/       # Workflow nodes
│   │   │   └── tools/       # Agent tools
│   │   ├── llm/             # LLM providers
│   │   │   ├── factory.py   # Multi-provider factory
│   │   │   └── providers/   # OpenAI, Anthropic, Google
│   │   ├── rag/             # Retrieval pipeline
│   │   │   ├── chunking.py  # Document chunking
│   │   │   ├── embeddings.py
│   │   │   └── retrieval.py # Hybrid search
│   │   ├── db/              # Database layer
│   │   └── core/            # Configuration
│   ├── tests/
│   └── alembic/             # Migrations
├── frontend/
│   ├── src/
│   │   ├── features/chat/   # Chat feature
│   │   ├── components/      # UI components
│   │   └── stores/          # Zustand stores
│   └── e2e/                 # Playwright tests
└── .claude/                 # AI development system
```

## Key Patterns

### Multi-Provider LLM Factory
```python
# Auto-detects provider from available API keys
from app.llm.factory import LLMFactory
llm = LLMFactory.create()  # Uses first available key
```

### LangGraph State
```python
class AgentState(TypedDict):
    query: str
    messages: Annotated[list[BaseMessage], operator.add]  # Parallel-safe
    retrieved_chunks: Annotated[list[Chunk], operator.add]
    response: str
```

### Langfuse Observability
```python
from langfuse.decorators import observe

@observe(name="my_function")
async def my_function():
    # Automatically traced
    pass
```

## Development Commands

```bash
make dev          # Start all services
make test         # Run all tests
make lint         # Check code quality
make migrate      # Run database migrations
```

## Agent System

This project includes 5 specialized Claude Code agents:

| Agent | Focus |
|-------|-------|
| backend-system-architect | REST APIs, databases, services |
| frontend-ui-developer | React components, state, UI |
| ai-ml-engineer | LLM integration, RAG, prompts |
| code-quality-reviewer | Testing, security, standards |
| studio-coach | Developer experience, tooling |

See `.claude/agents/` for full agent definitions.

## Skills

13 progressive-loading skills organized by category:

**Core**: `add-api-endpoint`, `add-database-model`, `add-react-component`, `write-tests`
**AI**: `add-llm-provider`, `create-agent-node`, `rag-pipeline`
**DevOps**: `docker-setup`, `ci-cd-pipeline`, `deployment`
**Quality**: `code-review`, `fix-bug`, `refactor-code`

## Code Quality Rules

1. **Type Safety**: All code must be fully typed
2. **Testing**: Maintain >90% coverage
3. **Security**: Follow OWASP Top 10
4. **Performance**: Use async/await for I/O
5. **Observability**: Trace all LLM calls

## Environment Variables

Required (at least one LLM key):
- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key
- `GOOGLE_API_KEY` - Google AI API key

See `.env.example` for full configuration.
