# Claude Code AI Development System

> Production-ready AI-assisted development configuration for Claude Code CLI.

This directory contains a comprehensive setup for AI-assisted development, including specialized agents, reusable skills, slash commands, hooks, and workflows.

## Quick Start

```bash
# Available slash commands
/commit          # Smart commit with validation
/create-pr       # Create PR with auto-generated description
/review-pr       # Comprehensive PR review
/implement       # Full-power feature implementation
/explore         # Deep codebase exploration
/brainstorm      # Multi-perspective idea exploration
/verify          # Comprehensive feature verification
/run-tests       # Test execution with analysis
/fix-issue       # Fix GitHub issues
/add-golden      # Add to golden dataset
```

## Directory Structure

```
.claude/
├── agents/          # 12 specialized subagents
├── commands/        # 10 slash commands (/commit, /review-pr, etc.)
├── hooks/           # Lifecycle & tool hooks
├── instructions/    # Guidelines & rules
├── schemas/         # JSON schemas for validation
├── skills/          # 30 reusable skill modules
├── templates/       # Reusable templates
├── workflows/       # Multi-step workflow definitions
├── context/         # Shared context between agents
├── agent-registry.json  # Agent definitions
└── settings.json    # Hook configuration
```

---

## Agents (12 Specialized Subagents)

Agents are specialized AI assistants that can be spawned for specific tasks.

| Agent | Purpose | Key Capabilities |
|-------|---------|------------------|
| `backend-system-architect` | API & system design | REST/GraphQL, microservices, scalability |
| `frontend-ui-developer` | React 19/TypeScript UI | Components, state, optimistic updates |
| `code-quality-reviewer` | Code review & QA | Bugs, security, best practices |
| `test-generator` | Test creation | Unit, integration, fixtures, mocking |
| `debug-investigator` | Root cause analysis | Scientific debugging, trace analysis |
| `security-auditor` | Security scanning | OWASP, vulnerabilities, secrets |
| `database-engineer` | PostgreSQL/pgvector | Schemas, migrations, optimization |
| `llm-integrator` | LLM integration | Prompts, function calling, streaming |
| `workflow-architect` | LangGraph workflows | Multi-agent, state, checkpointing |
| `data-pipeline-engineer` | Data processing | Embeddings, chunking, vectors |
| `ux-researcher` | User research | Personas, journeys, validation |
| `rapid-ui-designer` | UI/UX design | Tailwind, accessibility, mockups |

### Using Agents

Agents are automatically invoked via the `Task` tool based on task type:

```python
# Claude automatically selects appropriate agent
Task(
    subagent_type="code-quality-reviewer",
    prompt="Review the authentication module for security issues"
)
```

---

## Slash Commands (10 Available)

User-invokable commands for common workflows.

### Development Commands

| Command | Description |
|---------|-------------|
| `/commit` | Smart commit with validation and auto-generated message |
| `/create-pr` | Create PR with parallel validation and description |
| `/review-pr [number]` | Comprehensive PR review with multiple agents |
| `/implement [description]` | Full-power feature implementation |

### Quality Commands

| Command | Description |
|---------|-------------|
| `/verify` | Comprehensive feature verification |
| `/run-tests` | Run tests with parallel analysis |
| `/fix-issue [number]` | Fix GitHub issue with analysis |

### Research Commands

| Command | Description |
|---------|-------------|
| `/explore [query]` | Deep codebase exploration |
| `/brainstorm [topic]` | Multi-perspective idea exploration |
| `/add-golden [document]` | Add to golden dataset with validation |

---

## Skills (30 Reusable Modules)

Skills are domain-specific knowledge modules with templates and best practices.

### AI & LLM Skills

| Skill | Description |
|-------|-------------|
| `ai-native-development` | RAG, embeddings, agentic workflows |
| `langgraph-workflows` | Multi-agent patterns, state management |
| `langfuse-observability` | LLM tracing, evaluation, cost tracking |
| `llm-caching-patterns` | Semantic caching, cost optimization |
| `pgvector-search` | Hybrid search, embeddings, HNSW |

### Backend Skills

| Skill | Description |
|-------|-------------|
| `api-design-framework` | REST, GraphQL, OpenAPI |
| `database-schema-designer` | SQL, migrations, optimization |
| `streaming-api-patterns` | SSE, WebSockets, backpressure |
| `resilience-patterns` | Circuit breakers, retries, bulkheads |

### Frontend Skills

| Skill | Description |
|-------|-------------|
| `react-server-components-framework` | RSC, streaming, Server Actions |
| `type-safety-validation` | Zod, tRPC, exhaustive types |
| `design-system-starter` | Tokens, components, accessibility |
| `performance-optimization` | React 19, concurrent, bundles |

### DevOps & Quality

| Skill | Description |
|-------|-------------|
| `devops-deployment` | CI/CD, Docker, Kubernetes |
| `observability-monitoring` | Logging, metrics, tracing |
| `security-checklist` | OWASP, auth, validation |
| `testing-strategy-builder` | Unit, integration, E2E |
| `code-review-playbook` | Review process, checklists |

### Research & Documentation

| Skill | Description |
|-------|-------------|
| `brainstorming` | Socratic method, alternatives |
| `architecture-decision-record` | ADR templates, decisions |
| `browser-content-capture` | Playwright, SPA extraction |
| `github-cli` | Issues, PRs, Projects v2 |

---

## Hooks

Hooks are shell scripts that run at specific lifecycle points.

### Hook Types

| Hook Type | When It Runs | Purpose |
|-----------|--------------|---------|
| `PreToolUse` | Before tool execution | Validation, safety checks |
| `PostToolUse` | After tool execution | Logging, metrics |
| `PermissionRequest` | On permission prompt | Auto-approval for safe ops |
| `UserPromptSubmit` | On user message | Context injection |
| `SessionStart` | Session begins | Environment setup |
| `SessionEnd` | Session ends | Cleanup, metrics |
| `Stop` | On stop command | Context save |
| `SubagentStop` | Subagent completes | Quality gates |
| `Notification` | On notifications | Desktop alerts, sounds |

### Key Hooks

```
hooks/
├── pretool/
│   ├── bash/
│   │   ├── git-branch-protection.sh  # Prevent direct commits to main/dev
│   │   ├── issue-docs-requirement.sh # Ensure docs for issues
│   │   └── ci-simulation.sh          # Pre-run CI checks
│   ├── write-edit/
│   │   └── file-guard.sh             # Protect critical files
│   ├── task/
│   │   └── subagent-validator.sh     # Validate subagent usage
│   └── mcp/
│       ├── context7-tracker.sh       # Track Context7 usage
│       ├── memory-validator.sh       # Validate memory ops
│       └── playwright-safety.sh      # Browser safety checks
├── posttool/
│   ├── audit-logger.sh               # Log all tool usage
│   ├── session-metrics.sh            # Track metrics
│   └── error-tracker.sh              # Track errors
├── permission/
│   ├── auto-approve-readonly.sh      # Auto-approve Read/Glob/Grep
│   ├── auto-approve-safe-bash.sh     # Auto-approve safe commands
│   └── auto-approve-project-writes.sh # Auto-approve project file writes
├── lifecycle/
│   ├── session-context-loader.sh     # Load context on start
│   ├── session-env-setup.sh          # Setup environment
│   ├── session-metrics-summary.sh    # Summary on end
│   └── session-cleanup.sh            # Cleanup on end
└── notification/
    ├── desktop.sh                    # macOS notifications
    └── sound.sh                      # Audio notifications
```

---

## Instructions

Guidelines and rules that Claude follows.

| File | Purpose |
|------|---------|
| `context-initialization.md` | What to read at session start |
| `code-quality-rules.md` | Linting, formatting standards |
| `backend-code-quality-rules.md` | Python-specific rules |
| `architecture-decisions.md` | Key architectural patterns |
| `supervisor-rules.md` | Multi-agent coordination |
| `mcp-optimization.md` | MCP server usage patterns |

---

## Workflows

Pre-defined multi-step workflows for complex tasks.

| Workflow | Description |
|----------|-------------|
| `full-stack-feature.md` | End-to-end feature implementation |
| `secure-api-endpoint.md` | Security-first API development |
| `ai-integration.md` | Adding AI/LLM capabilities |

---

## Configuration

### settings.json

Configures hooks for various lifecycle events:

```json
{
  "hooks": {
    "PreToolUse": [...],      // Before each tool
    "PostToolUse": [...],     // After each tool
    "PermissionRequest": [...], // Permission prompts
    "UserPromptSubmit": [...], // User messages
    "SessionStart": [...],    // Session start
    "SessionEnd": [...],      // Session end
    "Stop": [...],            // Stop command
    "SubagentStop": [...],    // Subagent completion
    "Notification": [...]     // Notifications
  }
}
```

### agent-registry.json

Defines available agents with their capabilities and configurations.

---

## Best Practices

### 1. Use Slash Commands for Common Tasks

```bash
# Instead of manually committing:
/commit

# Instead of manually reviewing:
/review-pr 123
```

### 2. Let Claude Select Agents

Claude automatically selects the best agent for each task. Trust the agent selection.

### 3. Use Skills for Domain Knowledge

When working on specific domains (LLM integration, database design), skills provide templates and best practices.

### 4. Hooks Enforce Standards

Hooks automatically:
- Prevent direct commits to main/dev
- Run CI checks before commits
- Auto-approve safe operations
- Track metrics and logs

### 5. Context Initialization

At session start, Claude reads:
1. `docs/CURRENT_STATUS.md` - Current sprint status
2. `docs/ARCHITECTURE.md` - System architecture
3. Recent git history

---

## Adding New Components

### Adding a New Agent

1. Create `agents/my-agent.md` with:
   - Role description
   - Capabilities
   - Tools available
   - Output format

2. Register in `agent-registry.json`

### Adding a New Skill

1. Create `skills/my-skill/`:
   ```
   my-skill/
   ├── SKILL.md           # Skill documentation
   ├── capabilities.json  # Capabilities manifest
   ├── templates/         # Reusable templates
   └── references/        # Reference documentation
   ```

### Adding a New Command

1. Create `commands/my-command.md` with:
   - Command description
   - Usage examples
   - Implementation steps

### Adding a New Hook

1. Create script in appropriate `hooks/` subdirectory
2. Register in `settings.json`
3. Make executable: `chmod +x hooks/my-hook.sh`

---

## MCP Servers

This project uses the following MCP (Model Context Protocol) servers:

| Server | Purpose |
|--------|---------|
| `memory` | Knowledge graph for persistent context |
| `sequential-thinking` | Structured problem decomposition |
| `context7` | Up-to-date library documentation |
| `playwright` | Browser automation |
| `pg-aiguide` | PostgreSQL best practices |

Configure MCP servers in `.mcp.json` at project root.

---

## Troubleshooting

### Hooks Not Running

1. Check permissions: `chmod +x .claude/hooks/**/*.sh`
2. Verify `settings.json` syntax
3. Check hook script for errors

### Agent Not Selected

1. Check `agent-registry.json` for agent definition
2. Verify agent description matches task type
3. Use explicit `subagent_type` in Task tool

### Skill Not Found

1. Verify `capabilities.json` exists
2. Check skill name matches directory
3. Ensure `SKILL.md` is present

---

## Related Documentation

- [Claude Code Documentation](https://docs.anthropic.com/claude-code)
- [MCP Protocol](https://modelcontextprotocol.io)
- [Project README](../README.md)
- [Architecture](../docs/ARCHITECTURE.md)
