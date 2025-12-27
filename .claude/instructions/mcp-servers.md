# MCP Server Configuration

## Overview

YG Starter includes pre-configured MCP (Model Context Protocol) servers optimized for AI-powered development.

## Core Servers (~4,200 tokens)

The `.mcp.json` includes 3 core servers following Anthropic's recommendation:

| Server | Purpose | Token Cost |
|--------|---------|------------|
| **memory** | Conversation context persistence across sessions | ~2,000 |
| **sequential-thinking** | Advanced multi-step reasoning and analysis | ~700 |
| **context7** | Library documentation lookup (npm, frameworks, APIs) | ~1,500 |

## Adding Optional Servers

Copy configurations from `.mcp.json.example` as needed:

### PostgreSQL (Database Access)
```json
"postgres": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-postgres"],
  "env": {
    "POSTGRES_CONNECTION_STRING": "postgresql://dev:password@localhost:5447/yg-starter"
  }
}
```

### Playwright (Browser Automation)
```json
"playwright": {
  "command": "npx",
  "args": ["-y", "@playwright/mcp@latest"]
}
```

### Langfuse (Observability)
```json
"langfuse": {
  "type": "http",
  "url": "http://localhost:3010/api/public/mcp",
  "headers": {
    "Authorization": "Basic YOUR_BASE64_CREDENTIALS"
  }
}
```

## Best Practices

1. **Start minimal** - Use 3 core servers for most work
2. **Add selectively** - Enable task-specific servers only when needed
3. **Monitor usage** - Check `/context` in Claude Code regularly
4. **Remove when done** - Disable servers after completing specific tasks
5. **Keep to 2-5 servers** - Anthropic recommends this for best accuracy

## Monitoring Token Usage

Use `/context` in Claude Code to see:
- Total tokens consumed by MCP servers
- Which servers are currently active
- Token consumption per server

## References

- [Anthropic MCP Documentation](https://docs.anthropic.com/en/docs/claude-code/mcp)
- [MCP Server Catalog](https://github.com/modelcontextprotocol/servers)
