---
name: yg-starter
description: Production-ready AI application starter
version: 1.0.0
---

# YG Starter

> AI-powered full-stack application with multi-provider LLM, LangGraph agents, and Langfuse observability.

## WHY

Production-ready starter template for AI applications. Clone, customize with `./init.sh "Project Name"`, and start building.

## WHAT

**Stack**: React 19 + FastAPI + LangGraph + PostgreSQL/pgvector + Langfuse

**Ports**: Frontend `5183` | Backend `8600` | Postgres `5447` | Redis `6390` | Langfuse `3010`

## HOW

```bash
make dev      # Start all services
make test     # Run tests
make lint     # Check code quality
make down     # Stop services
```

---

## IMPORTANT: Context Initialization

**YOU MUST** read these files at the start of every session:
1. `docs/CURRENT_STATUS.md` - Sprint progress, blockers
2. `docs/ARCHITECTURE.md` - System design, patterns

Then run: `git log --oneline -10 && git status`

---

## IMPORTANT: Code Quality

**YOU MUST** run these before committing:

**Python**: `uv run ruff format --check app/ && uv run ruff check app/ && uv run ty check app/`

**TypeScript**: `npm run lint && npm run typecheck && npm run build`

---

## IMPORTANT: Git Workflow

- **NEVER** commit directly to `main` or `dev`
- Create feature branches: `feature/<name>` or `issue/<number>-<desc>`
- Use conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`

---

## Key Files

| Purpose | Location |
|---------|----------|
| Agent definitions | `.claude/agents/*.md` |
| Skills (12 total) | `.claude/skills/*/SKILL.md` |
| Parallel execution rules | `.claude/instructions/parallel-execution-rules.md` |
| Code quality rules | `.claude/instructions/code-quality-rules.md` |
| Context initialization | `.claude/instructions/context-initialization.md` |

---

## Agents (9 total)

Core: `backend-system-architect`, `frontend-ui-developer`, `ai-ml-engineer`, `code-quality-reviewer`

Support: `product-manager`, `rapid-ui-designer`, `sprint-prioritizer`, `ux-researcher`, `whimsy-injector`

---

## MCP Servers

Active: `memory`, `sequential-thinking`, `context7`

Config: `.mcp.json` | Docs: `.claude/instructions/mcp-servers.md`
