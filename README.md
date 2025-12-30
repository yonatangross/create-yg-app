# YG Starter

> Production-ready AI application starter with multi-provider LLM support, RAG, and full observability.

## Quick Start

```bash
# 1. Clone and initialize
git clone https://github.com/yonatangross/yg-starter.git my-project
cd my-project
./init.sh "My Project Name"

# 2. Add at least one LLM API key to backend/.env
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# GOOGLE_API_KEY=...

# 3. Start all services
make dev

# 4. Open the app
open http://localhost:5183
```

## What's Included

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.12 + FastAPI + LangGraph |
| **Frontend** | React 19 + Vite + TanStack + Tailwind |
| **Database** | PostgreSQL 17 + pgvector |
| **Cache** | Redis 7 (Stack) |
| **Observability** | Langfuse (self-hosted) |

## Services

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:5183 | Chat UI |
| Backend API | http://localhost:8600/docs | FastAPI Swagger |
| Langfuse | http://localhost:3010 | LLM Observability |
| MinIO Console | http://localhost:9011 | Blob Storage |

### Port Allocation

YG Starter uses offset ports to avoid conflicts with other local projects:

| Service | YG Starter | Standard | Offset |
|---------|------------|----------|--------|
| PostgreSQL | **5447** | 5432 | +15 |
| Redis | **6390** | 6379 | +11 |
| Backend | **8600** | 8000 | +600 |
| Frontend | **5183** | 5173 | +10 |
| Langfuse | **3010** | 3000 | +10 |
| MinIO API | **9010** | 9000 | +10 |
| MinIO Console | **9011** | 9001 | +10 |

> **Note**: All ports are configurable. See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for details.

## The init.sh Script

The initialization script:
1. **Generates cryptographic secrets** - All passwords, JWT tokens, encryption keys
2. **Creates backend/.env** - From backend/.env.example with real secrets
3. **Renames the project** - Updates all references (yg-starter → your-project)
4. **Resets git history** - Fresh start with initial commit
5. **Self-destructs** - Removes itself after running

Note: All environment configuration is consolidated in `backend/.env` (single source of truth).

## Development

```bash
# Start with hot reload
make dev

# Run tests
make test

# Code quality checks
make lint format typecheck

# Database migrations
make migrate
```

### Admin & Maintenance

```bash
# Cache management
make clear-cache      # Clear Redis cache
make cache-stats      # View cache statistics

# Memory management
make clear-memories   # Clear all memories
make memory-stats     # View memory statistics

# Database access
make db-shell         # Open PostgreSQL shell
make redis-shell      # Open Redis shell

# Usage statistics
make stats            # View overall usage stats

# Development utilities
make test-file FILE=tests/unit/test_example.py  # Run single test
make quality          # Check format, lint, and tests
```

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for full configuration options and tuning guide.

## Project Structure

```
your-project/
├── backend/           # FastAPI + LangGraph
│   ├── app/
│   │   ├── api/       # HTTP endpoints
│   │   ├── agent/     # LangGraph workflows
│   │   ├── llm/       # Multi-provider LLM
│   │   ├── rag/       # Retrieval pipeline
│   │   └── db/        # SQLAlchemy models
│   └── tests/
├── frontend/          # React 19 + TypeScript
│   ├── src/
│   │   ├── components/
│   │   ├── features/
│   │   └── stores/
│   └── e2e/
├── .claude/           # AI development system
│   ├── agents/        # 5 specialized agents
│   └── skills/        # 13 progressive skills
└── docker-compose.yml
```

## Claude Code Integration

This starter includes a pre-configured Claude Code AI development system:

- **5 Specialized Agents**: backend, frontend, AI/ML, quality, and DX
- **13 Progressive Skills**: Core, AI, DevOps, and Quality categories

See `.claude/` directory and `CLAUDE.md` for full configuration.

## License

MIT
