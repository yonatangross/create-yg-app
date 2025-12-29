# Configuration Guide

This guide covers all configuration options for YG Starter.

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://user:pass@localhost:5432/db` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `OPENAI_API_KEY` | OpenAI API key for embeddings and LLM | `sk-...` |

### Optional - LLM Providers

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM provider (openai, anthropic, google, xai) | `openai` |
| `LLM_MODEL` | Model name | `gpt-4o-mini` |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `GOOGLE_API_KEY` | Google AI API key | - |
| `XAI_API_KEY` | xAI API key | - |

### Optional - Context Engineering

| Variable | Description | Default |
|----------|-------------|---------|
| `MAX_CONTEXT_MESSAGES` | Max messages in context window | `20` |
| `EMBEDDING_CACHE_TTL` | Embedding cache TTL in seconds | `86400` (24h) |
| `MEMORY_SEARCH_THRESHOLD` | Min similarity for memory recall | `0.65` |
| `DATABASE_QUERY_TIMEOUT` | Query timeout in seconds | `30` |

### Optional - Rate Limiting & Security

| Variable | Description | Default |
|----------|-------------|---------|
| `RATE_LIMIT_PER_MINUTE` | Requests per minute per IP | `10` |
| `ADMIN_API_KEY` | Admin API authentication key | `dev-admin-key` |

### Optional - Database Tuning

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_POOL_SIZE` | Connection pool size | `20` |
| `DB_MAX_OVERFLOW` | Max overflow connections | `10` |
| `DB_POOL_RECYCLE` | Connection recycle time (seconds) | `3600` |

## Example .env File

```env
# Required
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5447/yg_starter
REDIS_URL=redis://localhost:6390/0
OPENAI_API_KEY=sk-your-key-here

# LLM Configuration
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini

# Context Engineering
MAX_CONTEXT_MESSAGES=20
EMBEDDING_CACHE_TTL=86400
MEMORY_SEARCH_THRESHOLD=0.65

# Security
ADMIN_API_KEY=your-secure-admin-key

# Development
DEBUG=true
LOG_LEVEL=INFO
```

## Feature Flags

Features can be enabled/disabled via configuration:

| Feature | Variable | Default |
|---------|----------|---------|
| Embedding Cache | `ENABLE_EMBEDDING_CACHE` | `true` |
| Memory Recall | `ENABLE_MEMORY_RECALL` | `true` |
| Usage Stats | `ENABLE_USAGE_STATS` | `true` |
| Rate Limiting | `ENABLE_RATE_LIMITING` | `true` |

## Tuning Guide

### For Development
- Use default settings
- `DEBUG=true` for verbose logging
- `RATE_LIMIT_PER_MINUTE=100` (or disable)

### For Production
- Set strong `ADMIN_API_KEY`
- Enable all caching
- `DB_POOL_SIZE=20` or higher based on load
- `DATABASE_QUERY_TIMEOUT=30` to prevent hanging queries

### For High Traffic
- `DB_POOL_SIZE=50`
- `EMBEDDING_CACHE_TTL=172800` (48h) for better hit rate
- Consider read replicas for memory search

## Admin Commands

### Cache Management

```bash
# Clear Redis cache (embeddings, artifacts)
make clear-cache

# View cache statistics
make cache-stats
```

### Memory Management

```bash
# Clear all memories from database
make clear-memories

# View memory statistics
make memory-stats
```

### Database Access

```bash
# Open PostgreSQL shell
make db-shell

# Open Redis shell
make redis-shell
```

### Usage Statistics

```bash
# View overall usage statistics
make stats

# View memory statistics
make memory-stats

# View cache statistics
make cache-stats
```

### Development Utilities

```bash
# Run a single test file
make test-file FILE=tests/unit/test_example.py

# Check all code quality (format, lint, tests)
make quality
```

## Port Configuration

YG Starter uses offset ports to avoid conflicts with other local projects (like SkillForge or default Docker services).

### Default Ports

| Service | YG Starter | Standard | Offset | Internal |
|---------|------------|----------|--------|----------|
| Frontend | **5183** | 5173 | +10 | 5173 |
| Backend API | **8600** | 8000 | +600 | 8600 |
| PostgreSQL | **5447** | 5432 | +15 | 5432 |
| Redis | **6390** | 6379 | +11 | 6379 |
| Langfuse Web | **3010** | 3000 | +10 | 3000 |
| MinIO API | **9010** | 9000 | +10 | 9000 |
| MinIO Console | **9011** | 9001 | +10 | 9001 |

### Port Comparison (YG Starter vs SkillForge)

If running both projects simultaneously:

| Service | YG Starter | SkillForge | Delta |
|---------|------------|------------|-------|
| PostgreSQL | 5447 | 5437 | +10 |
| Redis | 6390 | 6380 | +10 |
| Backend | 8600 | 8500 | +100 |
| Frontend | 5183 | 5173 | +10 |
| Langfuse | 3010 | 3000 | +10 |
| MinIO | 9010-9011 | 9000-9001 | +10 |

> **No conflicts**: Both projects can run simultaneously without port collisions.

## Observability

### Langfuse Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LANGFUSE_PUBLIC_KEY` | Langfuse public API key | Auto-generated |
| `LANGFUSE_SECRET_KEY` | Langfuse secret API key | Auto-generated |
| `LANGFUSE_HOST` | Langfuse host URL | `http://localhost:3010` |

### Logging

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `LOG_FORMAT` | Log format (json, text) | `json` |

## Troubleshooting

### Database Connection Issues

1. Check PostgreSQL is running: `docker compose ps postgres`
2. Verify DATABASE_URL matches docker-compose.yml ports
3. Check connection in PostgreSQL shell: `make db-shell`

### Redis Connection Issues

1. Check Redis is running: `docker compose ps redis`
2. Verify REDIS_URL matches docker-compose.yml ports
3. Test connection: `make redis-shell`

### LLM Provider Issues

1. Verify API key is set in .env
2. Check provider is supported: openai, anthropic, google, xai
3. Test with different model if current one fails

### Memory/Embedding Issues

1. Clear cache: `make clear-cache`
2. Clear memories: `make clear-memories`
3. Check embedding service is working
4. Verify OPENAI_API_KEY is set (required for embeddings)
