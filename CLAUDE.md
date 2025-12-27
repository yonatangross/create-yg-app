---
name: yg-starter
description: Production-ready AI application starter with multi-provider LLM, RAG, and full observability
version: 1.0.0
---

# YG Starter - AI Application Template

**Mode**: ⚡ Parallel Execution | **Discovery**: 🔍 Semantic Skills

## 🔄 MANDATORY: New Context Window Initialization

**EVERY TIME a new conversation/context window starts, YOU MUST:**

1. **Read** `.claude/instructions/context-initialization.md` for the full protocol
2. **Execute** the initialization steps before doing any work

**Quick Summary:**
- Read `docs/CURRENT_STATUS.md` → Current progress, blockers, completed work
- Read `docs/ARCHITECTURE.md` → Tech stack, patterns, decisions
- Check `git log --oneline -10` and `git status` → Recent changes
- Review `.claude/context/` → Decisions from previous sessions

**Full Protocol:** `.claude/instructions/context-initialization.md`

---

## 📦 Project Overview

**Production-ready AI application template** with multi-provider LLM support, RAG pipelines, and full observability via Langfuse.

**Stack**: React 19 + FastAPI + LangGraph 1.0 + PostgreSQL/PGVector + Langfuse

**Development Ports** (docker-compose.yml):
| Service | Port | URL |
|---------|------|-----|
| Frontend | 5183 | `http://localhost:5183` |
| Backend API | 8600 | `http://localhost:8600/docs` |
| PostgreSQL | 5447 | `localhost:5447` |
| Redis | 6390 | `localhost:6390` |
| Langfuse | 3010 | `http://localhost:3010` |

---

## 🏗️ Architecture

**Codebase Structure**:
```
yg-starter/
├── backend/                # FastAPI + LangGraph
│   ├── app/
│   │   ├── api/v1/         # REST endpoints
│   │   ├── agent/          # LangGraph workflows
│   │   │   ├── graph.py    # Main workflow
│   │   │   ├── state.py    # TypedDict state
│   │   │   └── nodes/      # Workflow nodes
│   │   ├── llm/            # Multi-provider factory
│   │   ├── core/           # Config, resilience
│   │   └── middleware/     # Rate limiting
│   └── tests/
├── frontend/               # React 19 + Vite
│   └── src/
│       ├── features/       # Feature modules
│       ├── components/     # UI components
│       └── stores/         # Zustand state
├── docs/                   # Documentation
└── .claude/                # AI development system
```

**Key Design Decisions**:
- Multi-provider LLM factory with automatic fallback
- LangGraph for stateful agent workflows
- Circuit breaker pattern for resilience
- File-based agent communication (no APIs between agents)
- Parallel execution via domain isolation

**Architecture Details:** `docs/ARCHITECTURE.md`

---

## 🤖 Agent System

**9 specialized agents** for different development tasks:

| Agent | Focus | Skills Used |
|-------|-------|-------------|
| `backend-system-architect` | APIs, databases, services | api-design, database-schema, security |
| `frontend-ui-developer` | React, components, state | testing, performance |
| `ai-ml-engineer` | LLM, RAG, LangGraph | langgraph, langfuse, pgvector |
| `code-quality-reviewer` | Testing, security, review | code-review, testing, security |
| `product-manager` | Requirements, roadmap | github-cli |
| `rapid-ui-designer` | Prototyping, wireframes | performance |
| `sprint-prioritizer` | Sprint planning | github-cli |
| `ux-researcher` | User research | - |
| `whimsy-injector` | Creative copy | - |

**Agent Definitions:** `.claude/agents/`
**Agent Registry:** `.claude/agent-registry.json`

---

## 🛠️ Skills (12 Production-Ready)

**Backend:**
- `api-design-framework` - REST/GraphQL patterns, versioning
- `database-schema-designer` - SQLAlchemy, migrations, indexes
- `streaming-api-patterns` - SSE, WebSockets, backpressure
- `resilience-patterns` - Circuit breakers, retries, fallbacks

**AI/ML:**
- `langgraph-workflows` - Multi-agent orchestration, checkpointing
- `langfuse-observability` - Tracing, evaluation, cost tracking
- `pgvector-search` - Embeddings, hybrid search, RRF

**Quality:**
- `code-review-playbook` - Review checklists, conventional comments
- `testing-strategy-builder` - Pytest, Vitest, coverage targets
- `security-checklist` - OWASP, auth patterns, input validation
- `performance-optimization` - Profiling, caching, bundle analysis

**DevOps:**
- `github-cli` - Issues, PRs, Projects v2, automation

**Skills Location:** `.claude/skills/`

---

## ⚡ Parallel Execution Rules

**CRITICAL: Follow `.claude/instructions/parallel-execution-rules.md`**

**Domain Isolation:**
- Backend agents: `backend/**` only
- Frontend agents: `frontend/**` only
- Never cross boundaries without explicit handoff

**File Locking:**
- One agent per file at a time
- Use `.claude/context/` for coordination
- Check `git status` before modifying shared files

---

## 📋 Code Quality Rules

**CRITICAL: Follow `.claude/instructions/code-quality-rules.md`**

### Python (Backend)
```bash
# MUST pass before commit:
uv run ruff format --check app/
uv run ruff check app/
uv run ty check app/
uv run pytest tests/ --cov=app
```

### TypeScript (Frontend)
```bash
# MUST pass before commit:
npm run lint
npm run typecheck
npm run build
```

### Git Workflow
- **Never commit directly to main/dev**
- Create feature branches: `feature/<name>` or `issue/<number>-<description>`
- PRs require passing CI checks
- Use conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`

---

## 🔧 Development Commands

```bash
# Start all services
make dev

# Run tests
make test

# Lint and format
make lint

# Database migrations
make migrate

# Stop all services
make down
```

---

## 🔍 MCP Servers

**Core (Active):** memory, sequential-thinking, context7

**Optional:** postgres, playwright, langfuse

**Configuration:** `.mcp.json`
**Documentation:** `.claude/instructions/mcp-servers.md`

---

## 📚 Key Documentation

| Document | Purpose |
|----------|---------|
| `docs/CURRENT_STATUS.md` | Sprint progress, blockers |
| `docs/ARCHITECTURE.md` | System design, patterns |
| `.claude/instructions/` | Agent behavior rules |
| `.claude/skills/` | Skill documentation |

---

## 🚀 Getting Started

```bash
# 1. Clone and setup
git clone <repo>
cd yg-starter
./init.sh "My Project"

# 2. Add API keys to .env
OPENAI_API_KEY=...
# or ANTHROPIC_API_KEY=...
# or GOOGLE_API_KEY=...

# 3. Start services
make dev

# 4. Access
# Frontend: http://localhost:5183
# Backend:  http://localhost:8600/docs
# Langfuse: http://localhost:3010
```

---

**Version:** 1.0.0 (December 2025)
**License:** MIT
