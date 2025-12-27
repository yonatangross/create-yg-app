"""Redis connection factory with robust connection pooling.

Issue #388: Production-ready Redis connection with TCP keepalive socket options.
Issue #2025: Added Redis ACL authentication patterns for fine-grained access control.

Fixes "Connection closed by server" errors by adding:
- TCP keepalive socket options (prevents idle connection drops)
- Socket keepalive boolean flag (enables keepalive)
- Connection/read timeouts (prevents hanging)
- Connection pool health checks (validates stale connections)
- Automatic retry with exponential backoff
- Redis ACL authentication support (2025 best practices)
"""

import socket
import sys

from redis import ConnectionPool, Redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _validate_redis_url(url: str) -> dict[str, str | None]:
    """Validate and parse Redis URL for ACL authentication patterns.

    Supports Redis ACL URLs in format: redis://[username]:[password]@host:port[/database]

    Args:
        url: Redis connection URL

    Returns:
        Dictionary with parsed URL components and validation info

    Raises:
        ValueError: If URL format is invalid for ACL authentication

    """
    if not url.startswith("redis://"):
        msg = f"Redis URL must start with 'redis://', got: {url}"
        raise ValueError(msg)

    # Parse URL components
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)

        result = {
            "scheme": parsed.scheme,
            "hostname": parsed.hostname,
            "port": str(parsed.port or 6379),
            "path": parsed.path or "/0",
            "username": parsed.username,
            "password": parsed.password,
        }

        # Validate ACL authentication pattern
        if parsed.username and parsed.password:
            # Full ACL authentication: redis://user:pass@host:port
            logger.info(
                "redis_acl_authentication_detected",
                username=parsed.username,
                has_password=bool(parsed.password),
                hostname=parsed.hostname,
                port=result["port"],
            )
        elif parsed.password and not parsed.username:
            # Password-only authentication: redis://:pass@host:port (default user)
            logger.info(
                "redis_password_authentication_detected",
                username="default",
                has_password=bool(parsed.password),
                hostname=parsed.hostname,
                port=result["port"],
            )
        else:
            # No authentication - development only
            logger.warning(
                "redis_no_authentication_configured",
                message="Consider enabling Redis authentication for security",
                hostname=parsed.hostname,
                port=result["port"],
            )

        return result

    except Exception as e:
        msg = f"Invalid Redis URL format: {url}. Error: {e}"
        raise ValueError(msg) from e


def create_redis_client(
    redis_url: str | None = None,
    **kwargs,
) -> Redis:
    """Create a Redis client with production-ready connection pooling.

    Supports Redis ACL authentication patterns (2025 best practices):
    - redis://username:password@host:port/database (full ACL)
    - redis://:password@host:port/database (default user with password)

    Configures:
    - TCP keepalive socket options (OS-level, prevents idle disconnections)
    - Socket keepalive boolean (enables keepalive)
    - Connection/read timeouts (prevents hanging)
    - Connection pool health checks (validates stale connections)
    - Automatic retry with exponential backoff (3 attempts)
    - Redis ACL authentication validation (2025)

    TCP Keepalive Configuration:
    - TCP_KEEPIDLE: 60 seconds before sending keepalive probe
    - TCP_KEEPINTVL: 10 seconds between keepalive probes
    - TCP_KEEPCNT: 3 failed probes before connection marked dead
    - Total timeout: 60 + (10 * 3) = 90 seconds

    Args:
        redis_url: Redis connection URL (defaults to settings.REDIS_URL)
        **kwargs: Additional connection pool parameters

    Returns:
        Configured Redis client instance

    Raises:
        ValueError: If Redis URL is invalid for ACL authentication

    Example:
        >>> client = create_redis_client()
        >>> await client.ping()  # Validates connection

        >>> # ACL authentication
        >>> client = create_redis_client("redis://myuser:mypass@redis:6379/0")

    """
    settings = get_settings()
    url = redis_url or settings.REDIS_URL

    # Validate Redis URL format and ACL authentication (2025 best practices)
    url_components = _validate_redis_url(url)

    # Extract configuration from kwargs or use settings
    socket_connect_timeout = kwargs.pop(
        "socket_connect_timeout",
        settings.REDIS_SOCKET_CONNECT_TIMEOUT,
    )
    socket_timeout = kwargs.pop(
        "socket_timeout",
        settings.REDIS_SOCKET_TIMEOUT,
    )
    socket_keepalive = kwargs.pop(
        "socket_keepalive",
        settings.REDIS_SOCKET_KEEPALIVE,
    )
    max_connections = kwargs.pop(
        "max_connections",
        settings.REDIS_MAX_CONNECTIONS,
    )
    health_check_interval = kwargs.pop(
        "health_check_interval",
        settings.REDIS_HEALTH_CHECK_INTERVAL,
    )

    # TCP keepalive socket options (OS-level configuration)
    # Platform-specific constants for socket.setsockopt()
    socket_keepalive_options = _get_socket_keepalive_options()

    logger.info(
        "redis_connection_factory_creating",
        redis_url_components=url_components,
        socket_keepalive=socket_keepalive,
        socket_keepalive_options=socket_keepalive_options,
        socket_timeout=socket_timeout,
        max_connections=max_connections,
        health_check_interval=health_check_interval,
    )

    # Create connection pool with proper configuration
    connection_pool = ConnectionPool.from_url(
        url,
        max_connections=max_connections,
        socket_connect_timeout=socket_connect_timeout,
        socket_timeout=socket_timeout,
        socket_keepalive=socket_keepalive,
        socket_keepalive_options=socket_keepalive_options,
        health_check_interval=health_check_interval,
        retry=Retry(
            backoff=ExponentialBackoff(),
            retries=3,
        ),
        **kwargs,
    )

    return Redis(connection_pool=connection_pool)


def _get_socket_keepalive_options() -> dict[int, int]:
    """Get platform-specific TCP keepalive socket options.

    Returns:
        Dictionary of socket options for TCP keepalive:
        - TCP_KEEPIDLE: Seconds before sending keepalive probe (60s)
        - TCP_KEEPINTVL: Seconds between keepalive probes (10s)
        - TCP_KEEPCNT: Number of failed probes before connection dead (3)

    Note:
        Options are platform-specific:
        - Linux: TCP_KEEPIDLE, TCP_KEEPINTVL, TCP_KEEPCNT
        - macOS: TCP_KEEPALIVE, TCP_KEEPINTVL, TCP_KEEPCNT
        - Windows: Uses different constant values

    """
    options = {}

    # TCP_KEEPIDLE or TCP_KEEPALIVE (macOS uses different constant name)
    if sys.platform == "darwin":  # macOS
        # macOS uses TCP_KEEPALIVE instead of TCP_KEEPIDLE
        options[socket.TCP_KEEPALIVE] = 60
    elif hasattr(socket, "TCP_KEEPIDLE"):  # Linux
        options[socket.TCP_KEEPIDLE] = 60
    # Windows doesn't support TCP_KEEPIDLE - keepalive is configured differently

    # TCP_KEEPINTVL: Interval between keepalive probes (10 seconds)
    if hasattr(socket, "TCP_KEEPINTVL"):
        options[socket.TCP_KEEPINTVL] = 10

    # TCP_KEEPCNT: Number of failed probes before connection is marked dead (3)
    if hasattr(socket, "TCP_KEEPCNT"):
        options[socket.TCP_KEEPCNT] = 3

    return options


def create_redis_client_with_acl(
    redis_url: str | None = None,
    username: str | None = None,
    password: str | None = None,
    **kwargs,
) -> Redis:
    """Create a Redis client with explicit ACL authentication parameters.

    Provides explicit ACL authentication for Redis 7.2+ fine-grained access control.
    Useful when you need to specify username/password separately from URL.

    Args:
        redis_url: Base Redis URL without credentials
        username: Redis ACL username (defaults to "default")
        password: Redis ACL password
        **kwargs: Additional connection pool parameters

    Returns:
        Configured Redis client with ACL authentication

    Example:
        >>> # Explicit ACL authentication
        >>> client = create_redis_client_with_acl(
        ...     "redis://redis:6379", username="skillforge-user", password="secure-password"
        ... )

    """
    if not redis_url:
        settings = get_settings()
        redis_url = settings.REDIS_URL

    # Remove any existing auth from URL
    if "://" in redis_url and "@" in redis_url:
        # Strip existing auth: redis://user:pass@host:port -> redis://host:port
        protocol, rest = redis_url.split("://", 1)
        host_port = rest.split("@", 1)[1]
        redis_url = f"{protocol}://{host_port}"

    # Construct ACL-authenticated URL
    auth_username = username or "default"
    if password:
        auth_url = f"redis://{auth_username}:{password}@{redis_url.replace('redis://', '')}"
    else:
        auth_url = redis_url  # No auth needed

    return create_redis_client(auth_url, **kwargs)


def get_redis_url_for_langchain() -> str:
    """Get Redis URL with connection parameters for LangChain components.

    LangChain's cache classes accept redis_url but need parameters passed differently.
    This returns the base URL - the create_redis_client should be used for direct Redis.
    """
    settings = get_settings()
    return settings.REDIS_URL
