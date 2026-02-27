"""Structured logging setup for LoadForge."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime


class _JsonFormatter(logging.Formatter):
    """Structured JSON log formatter.

    Emits one-line JSON objects with keys: timestamp, level, logger, message.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string.

        Args:
            record: The log record to format.

        Returns:
            A single-line JSON string.
        """
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging(
    level: int = logging.INFO,
    *,
    json_format: bool = False,
) -> logging.Logger:
    """Configure and return the root LoadForge logger.

    Sets up a handler on the ``loadforge`` logger namespace. Subsequent
    calls are idempotent — handlers are not duplicated.

    Args:
        level: Logging level (e.g., ``logging.DEBUG``). Defaults to INFO.
        json_format: If True, emit structured JSON logs. If False, emit
            human-readable logs.

    Returns:
        The configured ``loadforge`` root logger.
    """
    logger = logging.getLogger("loadforge")
    logger.setLevel(level)

    # Idempotent: update existing handler levels and return early
    if logger.handlers:
        for handler in logger.handlers:
            handler.setLevel(level)
        return logger

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)

    if json_format:
        formatter: logging.Formatter = _JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Prevent propagation to root logger to avoid duplicate output
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the ``loadforge`` namespace.

    Args:
        name: Logger name, appended to ``loadforge.`` prefix.
            Example: ``get_logger("engine.worker")`` returns
            ``logging.getLogger("loadforge.engine.worker")``.

    Returns:
        A configured child logger.
    """
    return logging.getLogger(f"loadforge.{name}")
