"""Configure structured logging with structlog."""

import logging
import sys

import structlog
import structlog.dev
import structlog.stdlib

from app.core.config import settings


def setup_logging() -> None:
    """Configure structured logging with structlog.

    Sets up structured logging with different renderers for development
    (console) and production (JSON) environments. Integrates with Python's
    standard logging library for compatibility with third-party libraries.

    Raises:
        TypeError: If LOG_LEVEL is invalid

    """
    try:
        # Validate log level
        log_level = getattr(logging, settings.LOG_LEVEL.upper(), None)
        if not isinstance(log_level, int):
            error_msg = (
                f"Invalid LOG_LEVEL: {settings.LOG_LEVEL}. "
                f"Must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL"
            )
            raise TypeError(error_msg)

        # Configure standard logging first
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=log_level,
            force=True,  # Override any existing configuration
        )

        # Configure structlog processors
        processors: list[object] = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
        ]

        # Different renderer for dev vs prod
        if settings.is_development():
            # Development: Human-readable console output
            processors.append(structlog.dev.ConsoleRenderer(colors=True))
        else:
            # Production: JSON output for log aggregation
            processors.append(structlog.processors.JSONRenderer())

        # Configure structlog with stdlib integration
        structlog.configure(
            processors=processors,  # type: ignore[arg-type]
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
            context_class=dict,
        )

    except Exception as e:
        # Fallback to basic logging if structlog setup fails
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            level=logging.INFO,
        )
        logging.error(f"Failed to setup structlog: {e}", exc_info=True)  # noqa: LOG015
        raise


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """Get a configured structlog logger instance.

    Args:
        name: Logger name (typically __name__ of the calling module)

    Returns:
        Configured structlog BoundLogger instance

    """
    logger: structlog.BoundLogger = structlog.get_logger(name)
    return logger


logger = get_logger(__name__)
