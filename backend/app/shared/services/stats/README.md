# Usage Statistics Service

Simple Redis-based usage tracking for monitoring application metrics.

## Features

- **Chat Tracking**: Count chat requests and token usage (daily + total)
- **Embedding Tracking**: Monitor embedding generation with cache hit rates
- **Memory Tracking**: Track memory recall operations and latency
- **Non-blocking**: All tracking is async and won't fail requests on errors

## Usage

### Track Chat Request

```python
from app.shared.services.stats.usage_stats import get_usage_stats

stats = get_usage_stats()
await stats.track_chat(
    conversation_id="conv_123",
    tokens_in=100,
    tokens_out=200
)
```

### Track Embedding

```python
# Cache hit
await stats.track_embedding(tokens=50, cached=True)

# Cache miss
await stats.track_embedding(tokens=50, cached=False)
```

### Track Memory Recall

```python
await stats.track_memory_recall(count=5, latency_ms=123.45)
```

### Get Statistics

```python
stats_data = await stats.get_stats()
# Returns:
# {
#     "chats": {"total": 100, "today": 10},
#     "tokens": {"input_total": 5000, "output_total": 8000},
#     "embeddings": {
#         "total": 200,
#         "cached": 160,
#         "cache_hit_rate": 80.0,
#         "tokens_used": 25000
#     },
#     "memory": {"recalls": 50, "items_recalled": 250},
#     "date": "2025-12-27"
# }
```

## API Endpoints

### Get Stats (Admin Only)

```bash
curl -X GET http://localhost:8600/api/v1/admin/stats/usage \
  -H "X-Admin-Key: your-admin-key"
```

### Reset Stats (Admin Only)

```bash
curl -X POST http://localhost:8600/api/v1/admin/stats/usage/reset \
  -H "X-Admin-Key: your-admin-key"
```

## Redis Keys

All stats are stored in Redis with the `stats:` prefix:

- `stats:chats:total` - Total chat count
- `stats:chats:YYYY-MM-DD` - Daily chat count
- `stats:tokens:in:total` - Total input tokens
- `stats:tokens:out:total` - Total output tokens
- `stats:embeddings:total` - Total embeddings
- `stats:embeddings:cached:total` - Cached embeddings
- `stats:embedding_tokens:total` - Total embedding tokens
- `stats:memory:recalls:total` - Total memory recalls

## Integration Points

Stats tracking is automatically integrated in:

1. **Chat Endpoints** (`/api/v1/chat`): Tracks all chat requests and token usage
2. **Embedding Cache** (`embedding_cache.py`): Tracks cache hits/misses
3. **Admin API** (`/api/v1/admin/stats/usage`): Exposes stats via REST API

## Error Handling

All tracking methods use try-except blocks to ensure stats failures don't impact core functionality:

```python
try:
    await stats.track_chat(...)
except Exception as e:
    logger.debug("stats_tracking_failed", error=str(e))
    # Request continues normally
```

## Testing

Run tests with:

```bash
uv run pytest tests/unit/test_usage_stats.py -v
```

## Future Enhancements

- Add per-user stats tracking
- Track response latencies
- Export stats to time-series database
- Add daily/weekly stat aggregations
- Dashboard visualization
